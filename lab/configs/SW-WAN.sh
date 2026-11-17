#!/bin/bash
set -eu
trap 'echo "BOOT_FAIL node=$HOSTNAME line=$LINENO command=$BASH_COMMAND" >&2' ERR
hostname SW-WAN
source /etc/fyp/secrets.sh
for attempt in $(seq 1 15); do ip link show eth0 >/dev/null 2>&1 && break; sleep 1; done
ip link set eth0 up
for attempt in $(seq 1 15); do ip link show eth1 >/dev/null 2>&1 && break; sleep 1; done
ip link set eth1 up
for attempt in $(seq 1 15); do ip link show eth2 >/dev/null 2>&1 && break; sleep 1; done
ip link set eth2 up
for attempt in $(seq 1 15); do ip link show eth3 >/dev/null 2>&1 && break; sleep 1; done
ip link set eth3 up
ip link set lo up
mkdir -p /var/run/openvswitch
test -f /etc/openvswitch/conf.db || ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
if ! pgrep -x ovsdb-server >/dev/null; then ovsdb-server --remote=punix:/var/run/openvswitch/db.sock --pidfile --detach; fi
ovs-vsctl --no-wait init
ovs-vsctl --no-wait set Open_vSwitch . other_config:n-handler-threads=1 other_config:n-revalidator-threads=1
if ! pgrep -x ovs-vswitchd >/dev/null; then ovs-vswitchd --pidfile --detach --log-file=/var/log/ovs.log; fi
ovs-vsctl --may-exist add-br br-lan
ovs-vsctl set bridge br-lan datapath_type=netdev rstp_enable=false
ovs-vsctl --may-exist add-port br-lan eth0
ovs-vsctl --may-exist add-port br-lan eth1
ovs-vsctl --may-exist add-port br-lan eth2
ovs-vsctl --may-exist add-port br-lan eth3
ip link set br-lan up
ip addr replace 10.0.0.254/24 dev br-lan
ip route replace default via 10.0.0.1
ip link set br-lan up
cat >/etc/rsyslog.conf <<'FYP_CONFIG'
module(load="imuxsock")
*.* action(type="omfwd" target="192.168.30.10" port="514" protocol="udp")
*.* /var/log/fyp-local.log
FYP_CONFIG
if ! pgrep -x rsyslogd >/dev/null; then rsyslogd -f /etc/rsyslog.conf -i /run/rsyslogd.pid; fi
cat >/etc/fyp/snmpd.conf <<SNMP
agentaddress udp:161
rocommunity $SNMP_COMMUNITY 192.168.30.10/32
sysName SW-WAN
sysLocation WAN
SNMP
if ! pgrep -x snmpd >/dev/null; then snmpd -C -c /etc/fyp/snmpd.conf -Lf /var/log/snmpd.log -p /run/snmpd.pid; fi
if ! test -f /run/fyp-link-monitor.pid || ! kill -0 "$(cat /run/fyp-link-monitor.pid)" 2>/dev/null; then
  (ip -ts monitor link | while IFS= read -r event; do logger -t link-state -- "$event"; done) >/dev/null 2>&1 </dev/null &
  echo $! >/run/fyp-link-monitor.pid
fi
logger -t fyp-bootstrap 'Node configuration ready'
