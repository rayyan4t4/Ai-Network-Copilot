#!/bin/bash
set -eu
trap 'echo "BOOT_FAIL node=$HOSTNAME line=$LINENO command=$BASH_COMMAND" >&2' ERR
hostname MON-HQ
source /etc/fyp/secrets.sh
for attempt in $(seq 1 15); do ip link show eth0 >/dev/null 2>&1 && break; sleep 1; done
ip link set eth0 up
ip link set lo up
ip addr replace 192.168.30.10/24 dev eth0
ip route replace default via 192.168.30.1
mkdir -p /var/log/fyp
cat >/etc/rsyslog.conf <<'FYP_CONFIG'
module(load="imuxsock")
module(load="imudp")
input(type="imudp" port="514")
template(name="CopilotJson" type="string" string="{\"event_time\":\"%timereported:::date-rfc3339%\",\"received_at\":\"%timegenerated:::date-rfc3339%\",\"source_ip\":\"%fromhost-ip:::json%\",\"hostname\":\"%hostname:::json%\",\"program\":\"%programname:::json%\",\"severity\":\"%syslogseverity%\",\"message\":\"%msg:::json%\",\"raw\":\"%rawmsg:::json%\"}\n")
*.* /var/log/fyp/received-syslog.log
*.* action(type="omfile" file="/var/log/fyp/telemetry.jsonl" template="CopilotJson")
FYP_CONFIG
if ! pgrep -x rsyslogd >/dev/null; then rsyslogd -f /etc/rsyslog.conf -i /run/rsyslogd.pid; fi
cat >/etc/fyp/snmpd.conf <<SNMP
agentaddress udp:161
rocommunity $SNMP_COMMUNITY 192.168.30.10/32
sysName MON-HQ
sysLocation HQ
SNMP
if ! pgrep -x snmpd >/dev/null; then snmpd -C -c /etc/fyp/snmpd.conf -Lf /var/log/snmpd.log -p /run/snmpd.pid; fi
if ! test -f /run/fyp-link-monitor.pid || ! kill -0 "$(cat /run/fyp-link-monitor.pid)" 2>/dev/null; then
  (ip -ts monitor link | while IFS= read -r event; do logger -t link-state -- "$event"; done) >/dev/null 2>&1 </dev/null &
  echo $! >/run/fyp-link-monitor.pid
fi
logger -t fyp-bootstrap 'Node configuration ready'
if test -f /opt/copilot/start.sh; then /bin/bash /opt/copilot/start.sh; fi
