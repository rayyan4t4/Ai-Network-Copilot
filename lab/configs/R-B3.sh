#!/bin/bash
set -eu
trap 'echo "BOOT_FAIL node=$HOSTNAME line=$LINENO command=$BASH_COMMAND" >&2' ERR
hostname R-B3
source /etc/fyp/secrets.sh
for attempt in $(seq 1 15); do ip link show eth0 >/dev/null 2>&1 && break; sleep 1; done
ip link set eth0 up
for attempt in $(seq 1 15); do ip link show eth1 >/dev/null 2>&1 && break; sleep 1; done
ip link set eth1 up
ip link set lo up
sysctl -qw net.ipv4.ip_forward=1
ip addr replace 10.13.0.1/30 dev eth0
ip addr replace 10.0.0.4/24 dev eth1
cat >/etc/frr/frr.conf <<'FYP_CONFIG'
frr defaults traditional
hostname R-B3
service integrated-vtysh-config
log syslog informational
interface eth0
 ip ospf network point-to-point
router ospf
 ospf router-id 4.4.4.4
 passive-interface default
 no passive-interface eth0
 log-adjacency-changes detail
 network 10.13.0.0/30 area 0
 no passive-interface eth1
 network 10.0.0.0/24 area 0
FYP_CONFIG
chown frr:frr /etc/frr/frr.conf
sed -i 's/^ospfd=no/ospfd=yes/' /etc/frr/daemons
cat >/etc/rsyslog.conf <<'FYP_CONFIG'
module(load="imuxsock")
*.* action(type="omfwd" target="192.168.30.10" port="514" protocol="udp")
*.* /var/log/fyp-local.log
FYP_CONFIG
if ! pgrep -x rsyslogd >/dev/null; then rsyslogd -f /etc/rsyslog.conf -i /run/rsyslogd.pid; fi
cat >/etc/fyp/snmpd.conf <<SNMP
agentaddress udp:161
rocommunity $SNMP_COMMUNITY 192.168.30.10/32
sysName R-B3
sysLocation B3
SNMP
if ! pgrep -x snmpd >/dev/null; then snmpd -C -c /etc/fyp/snmpd.conf -Lf /var/log/snmpd.log -p /run/snmpd.pid; fi
if pgrep -x watchfrr >/dev/null; then vtysh -b; else /usr/lib/frr/frrinit.sh start; fi
if ! test -f /run/fyp-link-monitor.pid || ! kill -0 "$(cat /run/fyp-link-monitor.pid)" 2>/dev/null; then
  (ip -ts monitor link | while IFS= read -r event; do logger -t link-state -- "$event"; done) >/dev/null 2>&1 </dev/null &
  echo $! >/run/fyp-link-monitor.pid
fi
logger -t fyp-bootstrap 'Node configuration ready'

# Study capacity baseline
tc qdisc replace dev eth1 root tbf rate 2mbit burst 32kb latency 100ms
