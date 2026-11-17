"""Generate declarative, restartable Linux/FRR/Open vSwitch node startup files."""
from topology_model import SITES, NODES
from gns3_api import ROOT

DHCP_HOOK = '''#!/bin/sh
set -eu
case "$1" in
  deconfig) ip -4 addr flush dev "$interface" ;;
  bound|renew)
    ip -4 addr flush dev "$interface"
    ip addr add "$ip/24" dev "$interface"
    ip link set "$interface" up
    if [ -n "${router:-}" ]; then ip route replace default via "${router%% *}" dev "$interface"; fi
    printf '%s\\n' "$ip" >/etc/fyp/lease-ip
    ;;
esac
'''

def heredoc(path, text):
    return f"cat >{path} <<'FYP_CONFIG'\n{text.rstrip()}\nFYP_CONFIG\n"

OVS_START = '''mkdir -p /var/run/openvswitch
test -f /etc/openvswitch/conf.db || ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
if ! pgrep -x ovsdb-server >/dev/null; then ovsdb-server --remote=punix:/var/run/openvswitch/db.sock --pidfile --detach; fi
ovs-vsctl --no-wait init
ovs-vsctl --no-wait set Open_vSwitch . other_config:n-handler-threads=1 other_config:n-revalidator-threads=1
if ! pgrep -x ovs-vswitchd >/dev/null; then ovs-vswitchd --pidfile --detach --log-file=/var/log/ovs.log; fi
ovs-vsctl --may-exist add-br br-lan
ovs-vsctl set bridge br-lan datapath_type=netdev rstp_enable=false
'''

def trunk(port):
    return f'ovs-vsctl --may-exist add-port br-lan {port} -- set port {port} vlan_mode=trunk trunks=10,20,30\n'
def access(port,vlan):
    return f'ovs-vsctl --may-exist add-port br-lan {port} -- set port {port} vlan_mode=access tag={vlan}\n'
def bond(a,b):
    return f'ovs-vsctl --may-exist add-bond br-lan bond1 {a} {b}\novs-vsctl set port bond1 lacp=active bond_mode=balance-slb vlan_mode=trunk trunks=10,20,30 other_config:lacp-time=fast\n'
def svi(vlan, ip):
    return f'ovs-vsctl --may-exist add-port br-lan vlan{vlan} -- set interface vlan{vlan} type=internal -- set port vlan{vlan} vlan_mode=access tag={vlan}\nip link set vlan{vlan} up\nip addr replace {ip}/24 dev vlan{vlan}\n'

def config(spec, macs):
    name,role=spec['name'],spec['role']
    site=next((s for s in SITES if s['name']==spec.get('site')),None)
    script=f'#!/bin/bash\nset -eu\ntrap \'echo "BOOT_FAIL node=$HOSTNAME line=$LINENO command=$BASH_COMMAND" >&2\' ERR\nhostname {name}\nsource /etc/fyp/secrets.sh\n'
    for p in range(spec['adapters']):
        script+=f'for attempt in $(seq 1 15); do ip link show eth{p} >/dev/null 2>&1 && break; sleep 1; done\nip link set eth{p} up\n'
    script+='ip link set lo up\n'
    if role=='host':
        script+=heredoc('/etc/fyp/dhcp-hook.sh',DHCP_HOOK)
        script+='chmod 755 /etc/fyp/dhcp-hook.sh\n'
        script+='if ! pgrep -x udhcpc >/dev/null; then udhcpc -b -i eth0 -p /run/udhcpc.pid -s /etc/fyp/dhcp-hook.sh -t 5 -T 2; fi\n'
        return script
    if role in ('wan','mls','access1','access2'):
        script+=OVS_START
        if role=='wan':
            for p in range(4): script+=f'ovs-vsctl --may-exist add-port br-lan eth{p}\n'
            script+='ip link set br-lan up\nip addr replace 10.0.0.254/24 dev br-lan\nip route replace default via 10.0.0.1\n'
        elif role=='mls':
            script+=bond('eth1','eth2')+trunk('eth3')
            for vlan,subnet in site['vlans'].items(): script+=svi(vlan,f'192.168.{subnet}.1')
        else:
            if role=='access1': script+=bond('eth0','eth1')+access('eth2',10)+access('eth3',20)
            else:
                script+=trunk('eth0')+access('eth1',30)
                if site['name']=='HQ': script+=access('eth2',30)
            script+=svi(30,spec['management_ip'])
            script+=f"ip route replace default via 192.168.{site['vlans'][30]}.1\n"
        script+='ip link set br-lan up\n'
    if role in ('router','mls'):
        script+='sysctl -qw net.ipv4.ip_forward=1\n'
        transit=site['transit']
        script+=f'ip addr replace {transit}.{1 if role=="router" else 2}/30 dev eth0\n'
        if role=='router': script+=f'ip addr replace 10.0.0.{site["index"]+1}/24 dev eth1\n'
        rid=(site['index']+1) * (1 if role=='router' else 11)
        frr=f'''frr defaults traditional
hostname {name}
service integrated-vtysh-config
log syslog informational
interface eth0
 ip ospf network point-to-point
router ospf
 ospf router-id {rid}.{rid}.{rid}.{rid}
 passive-interface default
 no passive-interface eth0
 log-adjacency-changes detail
 network {transit}.0/30 area 0
'''
        if role=='router': frr+=' no passive-interface eth1\n network 10.0.0.0/24 area 0\n'
        else:
            for subnet in site['vlans'].values(): frr+=f' network 192.168.{subnet}.0/24 area 0\n'
        script+=heredoc('/etc/frr/frr.conf',frr)
        script+="chown frr:frr /etc/frr/frr.conf\nsed -i 's/^ospfd=no/ospfd=yes/' /etc/frr/daemons\n"
    if role=='mls':
        admin,staff=site['vlans'][10],site['vlans'][20]
        script+='if nft list table inet fyp_policy >/dev/null 2>&1; then nft delete table inet fyp_policy; fi\n'
        script+="nft add table inet fyp_policy\nnft 'add chain inet fyp_policy forward { type filter hook forward priority 0; policy accept; }'\n"
        script+=f'nft add rule inet fyp_policy forward iifname vlan10 ip saddr 192.168.{admin}.0/24 ip daddr 192.168.{staff}.0/24 counter drop\n'
        dns='port=0\nbind-interfaces\ndhcp-authoritative\nlog-dhcp\ndhcp-leasefile=/etc/fyp/dnsmasq.leases\n'
        for vlan,subnet in site['vlans'].items():
            label={10:'ADMIN',20:'STAFF',30:'IT'}[vlan]
            host=f'PC-{site["name"]}-{label}'
            dns+=f'interface=vlan{vlan}\ndhcp-range=set:v{vlan},192.168.{subnet}.100,192.168.{subnet}.199,255.255.255.0,12h\ndhcp-option=tag:v{vlan},option:router,192.168.{subnet}.1\ndhcp-host={macs[host]},192.168.{subnet}.101,{host.lower()},infinite\n'
        dns+='dhcp-option=option:dns-server\n'
        script+=heredoc('/etc/fyp/dnsmasq.conf',dns)
    if role=='monitor':
        script+='ip addr replace 192.168.30.10/24 dev eth0\nip route replace default via 192.168.30.1\n'
    logging='module(load="imuxsock")\n'
    if role=='monitor':
        script+='mkdir -p /var/log/fyp\n'
        logging=(ROOT/'collector/rsyslog.conf').read_text()
    else:
        logging+='*.* action(type="omfwd" target="192.168.30.10" port="514" protocol="udp")\n*.* /var/log/fyp-local.log\n'
    script+=heredoc('/etc/rsyslog.conf',logging)
    script+='if ! pgrep -x rsyslogd >/dev/null; then rsyslogd -f /etc/rsyslog.conf -i /run/rsyslogd.pid; fi\n'
    script+='''cat >/etc/fyp/snmpd.conf <<SNMP
agentaddress udp:161
rocommunity $SNMP_COMMUNITY 192.168.30.10/32
sysName '''+name+'''
sysLocation '''+spec.get('site','WAN')+'''
SNMP
if ! pgrep -x snmpd >/dev/null; then snmpd -C -c /etc/fyp/snmpd.conf -Lf /var/log/snmpd.log -p /run/snmpd.pid; fi
'''
    if role in ('router','mls'):
        script+='if pgrep -x watchfrr >/dev/null; then vtysh -b; else /usr/lib/frr/frrinit.sh start; fi\n'
    if role=='mls': script+='if ! pgrep -x dnsmasq >/dev/null; then dnsmasq --conf-file=/etc/fyp/dnsmasq.conf --pid-file=/run/dnsmasq.pid; fi\n'
    script+='''if ! test -f /run/fyp-link-monitor.pid || ! kill -0 "$(cat /run/fyp-link-monitor.pid)" 2>/dev/null; then
  (ip -ts monitor link | while IFS= read -r event; do logger -t link-state -- "$event"; done) >/dev/null 2>&1 </dev/null &
  echo $! >/run/fyp-link-monitor.pid
fi
logger -t fyp-bootstrap 'Node configuration ready'
'''
    if role=='monitor':script+='if test -f /opt/copilot/start.sh; then /bin/bash /opt/copilot/start.sh; fi\n'
    return script
