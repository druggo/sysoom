#!/usr/bin/env python3
"""A skeleton for a Python rsyslog output plugin with error handling.
Requires Python 3.

To integrate a plugin based on this skeleton with rsyslog, configure an
'omprog' action like the following:
    action(type="omprog"
        binary="/usr/bin/myplugin.py"
        output="/var/log/myplugin.log"
        confirmMessages="on"
        ...)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0
     -or-
     see COPYING.ASL20 in the source distribution

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sys
import os
import logging
import re
import requests
import json


# Global definitions specific to your plugin
outfile = None
oom = {}

alertmanager_url = "http://alertmanager:9093/api/v2/alerts"

class RecoverableError(Exception):
    """An error that has caused the processing of the current message to
    fail, but does not require restarting the plugin.

    An example of such an error would be a temporary loss of connection to
    a database or a server. If such an error occurs in the onMessage function,
    your plugin should wrap it in a RecoverableError before raising it.
    For example:

        try:
            # code that connects to a database
        except DbConnectionError as e:
            raise RecoverableError from e

    Recoverable errors will cause the 'omprog' action to be temporarily
    suspended by rsyslog, during a period that can be configured using the
    "action.resumeInterval" action parameter. When the action is resumed,
    rsyslog will resend the failed message to your plugin.
    """


def onInit():
    """Do everything that is needed to initialize processing (e.g. open files,
    create handles, connect to systems...).
    """
    # Apart from processing the logs received from rsyslog, you want your plugin
    # to be able to report its own logs in some way. This will facilitate
    # diagnosing problems and debugging your code. Here we set up the standard
    # Python logging system to output the logs to stderr. In the rsyslog
    # configuration, you can configure the 'omprog' action to capture the stderr
    # of your plugin by specifying the action's "output" parameter.
    logging.basicConfig(stream=sys.stderr,
                        level=logging.WARNING,
                        format='%(asctime)s %(levelname)s %(message)s')

    # This is an example of a debug log. (Note that for debug logs to be
    # emitted you must set 'level' to logging.DEBUG above.)
    logging.debug("onInit called")

    # For illustrative purposes, this plugin skeleton appends the received logs
    # to a file. When implementing your plugin, remove the following code.
    global outfile
    outfile = open("/tmp/logfile", "w")


def onMessage(msg):
    """Process one log message received from rsyslog (e.g. send it to a
    database). If this function raises an error, the message will be retried
    by rsyslog.

    Args:
        msg (str): the log message. Does NOT include a trailing newline.

    Raises:
        RecoverableError: If a recoverable error occurs. The message will be
            retried without restarting the plugin.
        Exception: If a non-recoverable error occurs. The plugin will be
            restarted before retrying the message.
    """
    logging.debug("onMessage called")

    # For illustrative purposes, this plugin skeleton appends the received logs
    # to a file. When implementing your plugin, remove the following code.
    global outfile, oom
    
    mg=re.search(r'\S+\s+\S+\s+\S+\s+(\S+)\[(\S+)\]',msg)
    mg_hostname = mg.group(1)
    mg_ip = mg.group(2)
    if msg.find('invoked oom-killer') > 0:
        oom[mg_ip]={}
        oom[mg_ip]['hostname']=mg_hostname
        oom[mg_ip]['instance']=mg_ip
        oom[mg_ip]['msg']=[]
        oom[mg_ip]['process_list']=[]
        logging.error(msg)

    if mg_ip in oom:
        oom[mg_ip]['msg'].append(msg)
        if re.search(r'\[\s*\d+\]\s+[\d+\s+]{7,}\S+$',msg):
            mg=re.search(r'\s+(\S+)$',msg)
            oom[mg_ip]['process_list'].append(mg.group(1))

        if msg.find('global_oom') > 0:
            oom[mg_ip]['oom_memcg']='host'
            mg=re.search(r'task_memcg=([^,]+)',msg)
            oom[mg_ip]['task_memcg']=mg.group(1)

        elif msg.find('oom-kill:constraint=CONSTRAINT_MEMCG') > 0:
            mg=re.search(r'oom_memcg=([^,]+)',msg)
            oom[mg_ip]['oom_memcg']=mg.group(1)
            mg=re.search(r'task_memcg=([^,]+)',msg)
            oom[mg_ip]['task_memcg']=mg.group(1)


        if msg.find('Killed process') > 0:
            mg=re.search(r'Killed process \d+ \(([^(]+)\) total-vm:\S+, anon-rss:([^,]+)',msg)
            oom[mg_ip]['process']=mg.group(1)
            oom[mg_ip]['process_rss']=mg.group(2)

        if msg.find('Killed process') > 0:
            oom_msg = '\n'.join(map(str, oom[mg_ip]['msg']))
            logging.error(oom[mg_ip]['hostname'])
            logging.error(oom[mg_ip]['instance'])
            logging.error(oom[mg_ip]['oom_memcg'])
            logging.error(oom[mg_ip]['task_memcg'])
            logging.error(oom[mg_ip]['process'])
            logging.error(oom[mg_ip]['process_rss'])
            logging.error(' '.join(map(str, sorted(list(set(oom[mg_ip]['process_list']))))))

            alerts = [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "SysOOM",
                        "severity": "warning",
                        "job": "syslog-omprog",
                        "hostname": oom[mg_ip]['hostname'],
                        "instance": oom[mg_ip]['instance'],
                        "oom_memcg": oom[mg_ip]['oom_memcg'],
                        "task_memcg": oom[mg_ip]['task_memcg'],
                        "process": oom[mg_ip]['process'],
                        "process_rss": oom[mg_ip]['process_rss'],
                        "process_list": ' '.join(map(str, sorted(list(set(oom[mg_ip]['process_list'])))))
                    },
                    "annotations": {
                        "summary": oom[mg_ip]['hostname'] + " OOM kill detected",
                        "description": oom[mg_ip]['hostname'] + ": " + oom[mg_ip]['instance'] + " OOM killed : " + oom[mg_ip]['process']
                    },
                }
            ]

            try:
                response = requests.post(
                    alertmanager_url,
                    data=json.dumps(alerts),
                    headers={"Content-Type": "application/json"}
                )
            except Exception as e:
                print("发送告警失败")

            del oom[mg_ip]
            outfile.write(oom_msg)
            outfile.write("\n")
            outfile.flush()


def onExit():
    """Do everything that is needed to finish processing (e.g. close files,
    handles, disconnect from systems...). This is being called immediately
    before exiting.

    This function should not raise any error. If it does, the error will be
    logged as a warning and ignored.
    """
    logging.debug("onExit called")

    # For illustrative purposes, this plugin skeleton appends the received logs
    # to a file. When implementing your plugin, remove the following code.
    global outfile
    outfile.close()


"""
-------------------------------------------------------
This is plumbing that DOES NOT need to be CHANGED
-------------------------------------------------------
This is the main loop that receives messages from rsyslog via stdin,
invokes the above entrypoints, and provides status codes to rsyslog
via stdout. In most cases, modifying this code should not be necessary.
"""
try:
    onInit()
except Exception as e:
    # If an error occurs during initialization, log it and terminate. The
    # 'omprog' action will eventually restart the program.
    logging.exception("Initialization error, exiting program")
    sys.exit(1)

# Tell rsyslog we are ready to start processing messages:
print("OK", flush=True)

endedWithError = False
try:
    line = sys.stdin.readline()
    while line:
        line = line.rstrip('\n')
        try:
            onMessage(line)
            status = "OK"
        except RecoverableError as e:
            # Any line written to stdout that is not a status code will be
            # treated as a recoverable error by 'omprog', and cause the action
            # to be temporarily suspended. In this skeleton, we simply return
            # a one-line representation of the Python exception. (If debugging
            # is enabled in rsyslog, this line will appear in the debug logs.)
            status = repr(e)
            # We also log the complete exception to stderr (or to the logging
            # handler(s) configured in doInit, if any).
            logging.exception(e)

        # Send the status code (or the one-line error message) to rsyslog:
        print(status, flush=True)
        line = sys.stdin.readline()

except Exception:
    # If a non-recoverable error occurs, log it and terminate. The 'omprog'
    # action will eventually restart the program.
    logging.exception("Unrecoverable error, exiting program")
    endedWithError = True

try:
    onExit()
except Exception:
    logging.warning("Exception ignored in onExit", exc_info=True)

if endedWithError:
    sys.exit(1)
else:
    sys.exit(0)
