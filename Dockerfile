FROM ubuntu:noble

RUN  apt-get update -y \
     && apt-get install --no-install-recommends -y rsyslog python3-requests \
     && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY 11-imudp.conf 21-allsyslog.conf oom.py /etc/rsyslog.d/

RUN sed -i '/imklog/d' /etc/rsyslog.conf \
    && chmod 755 /etc/rsyslog.d/oom.py

CMD [ "/usr/sbin/rsyslogd", "-n"]
