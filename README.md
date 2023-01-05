# check_mailcow_rspamd
Icinga check command to check status of a Rspamd-Service in Mailcow

Heavily influenced by the great work of the [Monitoring Plugin Collection](https://github.com/Linuxfabrik/monitoring-plugins)

# installation

- copy script to /usr/lib/nagios/plugins/
- make script executable `chmod a+x ./check_mailcow_rspamd.py`
- define command in icinga

# help

```
usage: check_mailcow_rspamd.py [-h] [-V] [--always-ok] --server SERVER_ADDRESS [--count HISTORY_COUNT]
                               [--minBack MIN_BACK] [-c CRIT] [-w WARN] --apiKey API_KEY
This plugin lets you check the mailcow rspamd stats

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
  --always-ok           Always returns OK.
  --server SERVER_ADDRESS
                        Server address of your mailcow instance.
  --count HISTORY_COUNT
                        Count of Log entries that should be returned. Default: 200
  --minBack MIN_BACK    number of minutes to look back in logs. Default: 5
  -c CRIT, --critical CRIT
                        Set the critical threshold seconds since last connection update. Default: 3600
  -w WARN, --warning WARN
                        Set the warning threshold seconds since last connection update. Default: 1800
  --apiKey API_KEY      Mailcow apiKey. Can be generated in Mailcow UI
```
# usage example

```
./check_mailcow_rspamd.py --server https://mailcow.example.com --apiKey AAAAAA-BBBBBB-CCCCCC-DDDDDD-EEEEEE
```

# output

```
OK - 541s since last mail|'reject'=0;;;0; 'soft reject'=0;;;0; 'rewrite subject'=0;;;0; 'add header'=0;;;0; 'greylist'=0;;;0; 'no action'=0;;;0; 'total'=0;;;0;
```

# Reference
- [Monitoring Plugins Collection](https://github.com/Linuxfabrik/monitoring-plugins)
- [Mailcow Docs](https://docs.mailcow.email/manual-guides/Rspamd/u_e-rspamd/)
