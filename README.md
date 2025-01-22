# sysOOM
Send details to [alertmanager](https://github.com/prometheus/alertmanager) when OOM event occurs.

## How to use
  - Start sysOOM, replace 10.0.0.3 with your own alertmanager ip

    ``docker run -p 5149:5149/udp --add-host alertmanager:10.0.0.3 -d --restart=always --name sysoom druggo/sysoom``
    
  - Forward kernel log to sysOOM, replace 10.0.0.4 with sysOOM container's host ip

    ``echo ':syslogtag, startswith, "kernel" @10.0.0.4:5149' > /etc/rsyslog.d/41-kernel.conf``

  - Test OOM

    ``systemd-run --user --scope -p MemoryMax=1K vi /var/log/syslog``
