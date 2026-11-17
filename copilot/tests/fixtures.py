"""Explicit synthetic unit fixtures using the lab topology, never final trials."""
import copy
import json
import uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path

AT=datetime(2026,11,16,19,0,tzinfo=timezone.utc)
def when(seconds=0):return (AT-timedelta(seconds=seconds)).isoformat()
def uid(value):return str(uuid.uuid5(uuid.NAMESPACE_DNS,value))

def healthy():
    inv=json.loads((Path(__file__).resolve().parents[2]/'lab/topology/inventory.json').read_text())
    devices=[]
    for name,s in inv['nodes'].items():
        aliases=[s.get('management_ip') or s.get('expected_ip')]
        if s['role'] in ('router','mls'):
            site=next(x for x in inv['sites'] if x['name']==s['site']);aliases.append(site['transit']+('.1' if s['role']=='router' else '.2'))
        devices.append({'device_id':name,'hostname':name,'site':s.get('site','WAN'),'role':s['role'],'metadata':s,
          'management_ip':s.get('management_ip') or s.get('expected_ip'),'monitored':s['role'] not in ('host','monitor'),'aliases':aliases})
    links=[{'link_id':uid(str(i)), 'a_device':l['a'],'a_interface':'eth'+str(l['a_port']), 'b_device':l['b'],'b_interface':'eth'+str(l['b_port']),'purpose':l['purpose']} for i,l in enumerate(inv['links'])]
    ports=sorted({(l[side+'_device'],l[side+'_interface']) for l in links for side in ('a','b')})
    b={'schema_version':'copilot.1','as_of':when(),'devices':devices,'links':links,'interfaces':[],'polls':[],'samples':[],'probes':[],'events':[],'snapshots':[],'heartbeats':[],'counts':{}}
    for d in devices:
        if d['monitored']:b['polls'].append({'device_id':d['device_id'],'poll_id':uid(d['device_id']),'observed_at':when(2),'status':'ok'})
        if d['role']!='monitor':
            for age in (1,11):b['probes'].append({'device_id':d['device_id'],'probe_id':uid(d['device_id']+str(age)),'observed_at':when(age),'status':'ok','source_ip':'192.168.30.10','rtt_ms':1})
    for device,name in ports:
        if next(d for d in devices if d['device_id']==device)['monitored']:
            ident=device+':'+name
            b['interfaces'].append({'interface_id':ident,'device_id':device,'name':name,'capacity_source':'snmp'})
            b['samples'].append({'device_id':device,'interface_id':ident,'poll_id':uid(device),'observed_at':when(2),'admin_status':1,'oper_status':1,'rate_status':'valid',
              'in_bps':1000,'out_bps':1000,'in_utilization_pct':.01,'out_utilization_pct':.01,'speed_bps':10000000,'interval_s':30})
    for device,address,peer in [('R-B1','10.11.0.1','10.11.0.2'),('MLS-B1','10.11.0.2','10.11.0.1')]:
        b['snapshots'].append(snapshot(device,{'addresses':[{'ifname':'eth0','flags':['UP'],'operstate':'UNKNOWN','addr_info':[{'family':'inet','local':address,'prefixlen':30}]}],
          'ospf_neighbors':{'neighbors':{'neighbor':[{'address':peer,'state':'Full/-'}]}}}))
    return b

def snapshot(device,commands,age=1):
    return {'device_id':device,'snapshot_id':uid(device+'snap'+str(age)),'observed_at':when(age),'source':'authorized_readonly_console',
      'raw':{k:{'exit_code':0,'stdout':json.dumps(v),'stderr':''} for k,v in commands.items()}}

def outage():
    b=healthy()
    next(s for s in b['samples'] if s['interface_id']=='R-B1:eth0').update(admin_status=2,oper_status=2)
    s=next(s for s in b['snapshots'] if s['device_id']=='R-B1');addresses=json.loads(s['raw']['addresses']['stdout']);addresses[0]['flags']=[];s['raw']['addresses']['stdout']=json.dumps(addresses)
    for p in b['probes']:
        if p['device_id'].startswith(('MLS-B1','SW-B1','PC-B1')):p['status']='timeout'
    b['events']=[{'event_id':uid('down-event'),'device_id':'R-B1','received_at':when(3),'program':'link-state',
      'message':'123: eth0: <BROADCAST,MULTICAST> mtu 1500 state DOWN group default','identity_status':'source_and_hostname','parse_error':None},
      {'event_id':uid('ospf-event'),'device_id':'R-B1','received_at':when(3),'program':'ospfd',
      'message':'AdjChg: Nbr 22.22.22.22 on eth0:10.11.0.1: Full -> Deleted (KillNbr)','identity_status':'source_and_hostname','parse_error':None}]
    return b
