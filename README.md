# sysOOM
Send details to [alertmanager](https://github.com/prometheus/alertmanager) when OOM event occurs
```
  "labels": {
        "oom_memcg": "host",
        "task_memcg": "/user.slice/user-100.slice/run-wiki.scope",
        "process": "java",
        "hostname": "wiki2",
        "instance": "10.0.0.4",
        "severity": "warning",
        "alertname": "SysOOM",
        "process_rss": "165564kB",
        "process_list": "systemd-logind getty systemd-network systemd systemd-udevd java rsyslogd"
      }
```

## Basic use
  - Start sysOOM, replace 10.0.0.3 with your own alertmanager ip

    ``docker run -p 5149:5149/udp --add-host alertmanager:10.0.0.3 -d --restart=always --name sysoom ghcr.io/druggo/sysoom``
    
  - Forward kernel log to sysOOM, replace 10.0.0.4 with sysOOM container's host ip and reload rsyslog

    ``echo ':syslogtag, startswith, "kernel" @10.0.0.4:5149' > /etc/rsyslog.d/41-kernel.conf``

  - Test OOM

    ``systemd-run --user --scope -p MemoryMax=1K vi /var/log/syslog``

## Suppress node-exporter's NodeOOM
  - Ensure the syslog hostname matches the node-exporter hostname label
  - Add inhibit_rules to alertmanager.yml so that NodeOOM alert will supressed when SysOOM is fired
    
    ```
    - "equal":
      - "hostname"
      - "severity"
      "source_matchers":
      - "alertname = SysOOM"
      "target_matchers":
      - "alertname = NodeOOM"
    ```
