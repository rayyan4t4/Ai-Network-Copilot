"""Source of truth for the four-site, 30-node lightweight topology."""
import json
from gns3_api import ROOT

NAME = 'AI Network Copilot - Four Site Lightweight Lab'
IMAGE = 'fyp-network-node:1.0'
SITES = [
    {'name':'HQ','index':0,'vlans':{10:10,20:20,30:30},'transit':'10.10.0','x':-900},
    {'name':'B1','index':1,'vlans':{10:110,20:120,30:130},'transit':'10.11.0','x':-300},
    {'name':'B2','index':2,'vlans':{10:210,20:220,30:230},'transit':'10.12.0','x':300},
    {'name':'B3','index':3,'vlans':{10:31,20:32,30:33},'transit':'10.13.0','x':900},
]
NODES, LINKS = {}, []
def node(name, role, adapters, x, y, **extra):
    NODES[name] = {'name':name,'role':role,'adapters':adapters,'x':x,'y':y,**extra}
def link(a, ap, b, bp, purpose):
    LINKS.append({'a':a,'a_port':ap,'b':b,'b_port':bp,'purpose':purpose})

node('SW-WAN','wan',4,0,-550,management_ip='10.0.0.254',gateway='10.0.0.1')
for s in SITES:
    site, idx, x, vlans = s['name'],s['index'],s['x'],s['vlans']
    node('R-'+site,'router',2,x,-380,site=site,management_ip=f'10.0.0.{idx+1}')
    node('MLS-'+site,'mls',4,x,-180,site=site,management_ip=f'192.168.{vlans[30]}.1')
    node(f'SW-{site}-1','access1',4,x-110,40,site=site,management_ip=f'192.168.{vlans[30]}.2')
    node(f'SW-{site}-2','access2',3 if site=='HQ' else 2,x+130,40,site=site,management_ip=f'192.168.{vlans[30]}.3')
    for vlan, label, offset in ((10,'ADMIN',-200),(20,'STAFF',-30),(30,'IT',160)):
        node(f'PC-{site}-{label}','host',1,x+offset,230,site=site,vlan=vlan,
             expected_ip=f'192.168.{vlans[vlan]}.101',gateway=f'192.168.{vlans[vlan]}.1')
    link('R-'+site,1,'SW-WAN',idx,'Shared OSPF WAN')
    link('R-'+site,0,'MLS-'+site,0,'Routed /30 uplink')
    link('MLS-'+site,1,f'SW-{site}-1',0,'LACP member 1')
    link('MLS-'+site,2,f'SW-{site}-1',1,'LACP member 2')
    link('MLS-'+site,3,f'SW-{site}-2',0,'VLAN trunk 10 20 30')
    link(f'SW-{site}-1',2,f'PC-{site}-ADMIN',0,'Access VLAN 10')
    link(f'SW-{site}-1',3,f'PC-{site}-STAFF',0,'Access VLAN 20')
    link(f'SW-{site}-2',1,f'PC-{site}-IT',0,'Access VLAN 30')
node('MON-HQ','monitor',1,-650,350,site='HQ',management_ip='192.168.30.10',gateway='192.168.30.1',image='fyp-monitor:1.0')
link('SW-HQ-2',2,'MON-HQ',0,'Monitoring server VLAN 30')
assert len(NODES)==30 and len(LINKS)==33
ports=set()
for l in LINKS:
    for name, port in ((l['a'],l['a_port']),(l['b'],l['b_port'])):
        assert port < NODES[name]['adapters']
        assert (name,port) not in ports
        ports.add((name,port))

def save_model():
    dest=ROOT/'.local/topology'; dest.mkdir(parents=True,exist_ok=True)
    (dest/'inventory.json').write_text(json.dumps({'name':NAME,'image':IMAGE,'sites':SITES,'nodes':NODES,'links':LINKS},indent=2))
    lines=['# Physical port map','', '| Node A | Port | Node B | Port | Purpose |','| --- | --- | --- | --- | --- |']
    lines += [f'| {l["a"]} | eth{l["a_port"]} | {l["b"]} | eth{l["b_port"]} | {l["purpose"]} |' for l in LINKS]
    (dest/'Port Map.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    save_model(); print(f'{len(NODES)} nodes, {len(LINKS)} links; port uniqueness verified.')
