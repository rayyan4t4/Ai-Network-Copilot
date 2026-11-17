#!/bin/bash
set -eu
trap 'echo "BOOT_FAIL node=$HOSTNAME line=$LINENO command=$BASH_COMMAND" >&2' ERR
hostname MLS-B1
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
ovs-vsctl --may-exist add-bond br-lan bond1 eth1 eth2
ovs-vsctl set port bond1 lacp=active bond_mode=balance-slb vlan_mode=trunk trunks=10,20,30 other_config:lacp-time=fast
ovs-vsctl --may-exist add-port br-lan eth3 -- set port eth3 vlan_mode=trunk trunks=10,20,30
ovs-vsctl --may-exist add-port br-lan vlan10 -- set interface vlan10 type=internal -- set port vlan10 vlan_mode=access tag=10
ip link set vlan10 up
ip addr replace 192.168.110.1/24 dev vlan10
ovs-vsctl --may-exist add-port br-lan vlan20 -- set interface vlan20 type=internal -- set port vlan20 vlan_mode=access tag=20
ip link set vlan20 up
ip addr replace 192.168.120.1/24 dev vlan20
ovs-vsctl --may-exist add-port br-lan vlan30 -- set interface vlan30 type=internal -- set port vlan30 vlan_mode=access tag=30
ip link set vlan30 up
ip addr replace 192.168.130.1/24 dev vlan30
ip link set br-lan up
sysctl -qw net.ipv4.ip_forward=1
ip addr replace 10.11.0.2/30 dev eth0
cat >/etc/frr/frr.conf <<'FYP_CONFIG'
frr defaults traditional
hostname MLS-B1
service integrated-vtysh-config
log syslog informational
interface eth0
 ip ospf network point-to-point
router ospf
 ospf router-id 22.22.22.22
 passive-interface default
 no passive-interface eth0
 log-adjacency-changes detail
 network 10.11.0.0/30 area 0
 network 192.168.110.0/24 area 0
 network 192.168.120.0/24 area 0
 network 192.168.130.0/24 area 0
FYP_CONFIG
chown frr:frr /etc/frr/frr.conf
sed -i 's/^ospfd=no/ospfd=yes/' /etc/frr/daemons
if nft list table inet fyp_policy >/dev/null 2>&1; then nft delete table inet fyp_policy; fi
nft add table inet fyp_policy
nft 'add chain inet fyp_policy forward { type filter hook forward priority 0; policy accept; }'
nft add rule inet fyp_policy forward iifname vlan10 ip saddr 192.168.110.0/24 ip daddr 192.168.120.0/24 counter drop
cat >/etc/fyp/dnsmasq.conf <<'FYP_CONFIG'
port=0
bind-interfaces
dhcp-authoritative
log-dhcp
dhcp-leasefile=/etc/fyp/dnsmasq.leases
interface=vlan10
dhcp-range=set:v10,192.168.110.100,192.168.110.199,255.255.255.0,12h
dhcp-option=tag:v10,option:router,192.168.110.1
dhcp-host=02:42:17:14:ca:00,192.168.110.101,pc-b1-admin,infinite
interface=vlan20
dhcp-range=set:v20,192.168.120.100,192.168.120.199,255.255.255.0,12h
dhcp-option=tag:v20,option:router,192.168.120.1
dhcp-host=02:42:09:c0:c8:00,192.168.120.101,pc-b1-staff,infinite
interface=vlan30
dhcp-range=set:v30,192.168.130.100,192.168.130.199,255.255.255.0,12h
dhcp-option=tag:v30,option:router,192.168.130.1
dhcp-host=02:42:7f:ee:08:00,192.168.130.101,pc-b1-it,infinite
dhcp-option=option:dns-server
FYP_CONFIG
cat >/etc/rsyslog.conf <<'FYP_CONFIG'
module(load="imuxsock")
*.* action(type="omfwd" target="192.168.30.10" port="514" protocol="udp")
*.* /var/log/fyp-local.log
FYP_CONFIG
if ! pgrep -x rsyslogd >/dev/null; then rsyslogd -f /etc/rsyslog.conf -i /run/rsyslogd.pid; fi
cat >/etc/fyp/snmpd.conf <<SNMP
agentaddress udp:161
rocommunity $SNMP_COMMUNITY 192.168.30.10/32
sysName MLS-B1
sysLocation B1
SNMP
if ! pgrep -x snmpd >/dev/null; then snmpd -C -c /etc/fyp/snmpd.conf -Lf /var/log/snmpd.log -p /run/snmpd.pid; fi
if pgrep -x watchfrr >/dev/null; then vtysh -b; else /usr/lib/frr/frrinit.sh start; fi
if ! pgrep -x dnsmasq >/dev/null; then dnsmasq --conf-file=/etc/fyp/dnsmasq.conf --pid-file=/run/dnsmasq.pid; fi
if ! test -f /run/fyp-link-monitor.pid || ! kill -0 "$(cat /run/fyp-link-monitor.pid)" 2>/dev/null; then
  (ip -ts monitor link | while IFS= read -r event; do logger -t link-state -- "$event"; done) >/dev/null 2>&1 </dev/null &
  echo $! >/run/fyp-link-monitor.pid
fi
logger -t fyp-bootstrap 'Node configuration ready'
