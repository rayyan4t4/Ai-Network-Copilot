"""Verify real network behavior and save pass/fail evidence for the full lab."""
import json
import shlex
import time
import uuid
from datetime import datetime, timezone
from gns3_api import ROOT, VM, api, make_ssh_client
from topology_model import SITES,NODES
import paramiko

deployment=json.loads((ROOT/'.local/deployment.json').read_text())
pid=deployment['project_id']
nodes={n['name']:n for n in api(f'/projects/{pid}/nodes')}
client=make_ssh_client()
results=[]
syslog_marker='NETWORK_BASELINE_CHECK_'+uuid.uuid4().hex
def run(cmd, input_text=None):
    i,o,e=client.exec_command(cmd,timeout=150)
    if input_text is not None:i.write(input_text);i.flush();i.channel.shutdown_write()
    stdout=o.read().decode(errors='replace');stderr=e.read().decode(errors='replace')
    return o.channel.recv_exit_status(),stdout,stderr
def inside(name,text):
    return run('sudo -n docker exec -i '+shlex.quote(nodes[name]['properties']['container_id'])+' /bin/bash -s',text)
def record(test,passed,details):
    results.append({'test':test,'passed':bool(passed),'details':details})
    print(('PASS ' if passed else 'FAIL ')+test,flush=True)
def scriptcheck(name,label,script):
    code,out,err=inside(name,script)
    record(label,code==0,{'node':name,'stdout':out,'stderr':err,'exit_code':code})
    return out

try:
    record('30 nodes started',len(nodes)==30 and all(n['status']=='started' for n in nodes.values()),{n['name']:n['status'] for n in nodes.values()})
    deadline=time.time()+80
    while True:
        code,out,err=inside('MON-HQ','ping -c 1 -W 1 192.168.33.1 >/dev/null\n')
        if code==0 or time.time()>deadline: break
        time.sleep(3)
    for name,spec in NODES.items():
        if spec['role'] in ('mls','access1'):
            deadline=time.time()+40
            while True:
                code,out,err=inside(name,'ovs-appctl lacp/show bond1\n')
                if code==0 and 'active negotiated' in out and out.count('may_enable: true')==2: break
                if time.time()>deadline: break
                time.sleep(2)
    for name,spec in NODES.items():
        if spec['role']=='host':
            host_script=f'''set -eu
ip -4 -o addr show dev eth0
test "$(cat /etc/fyp/lease-ip)" = {spec['expected_ip']}
ping -c 1 -W 2 {spec['gateway']}
ping -c 1 -W 2 192.168.30.10
'''
            attempts=[]
            for attempt in range(5):
                code,out,err=inside(name,host_script)
                attempts.append({'exit_code':code,'stdout':out,'stderr':err})
                if code==0:break
                time.sleep(2)
            record(name+' DHCP and gateway',code==0,{'attempts':attempts})
    hosts=[n for n in NODES if NODES[n]['role']=='host']
    for src in hosts:
        script=''
        for dst in hosts:
            if src==dst:continue
            script+=f"if ping -c 1 -W 1 {NODES[dst]['expected_ip']} >/dev/null 2>&1; then echo '{dst}|reachable'; else echo '{dst}|blocked'; fi\n"
        code,out,err=inside(src,script)
        actual=dict(line.split('|',1) for line in out.splitlines() if '|' in line)
        for dst in hosts:
            if src==dst:continue
            a,b=NODES[src],NODES[dst]
            blocked=a['site']==b['site'] and {a['vlan'],b['vlan']}=={10,20}
            expected='blocked' if blocked else 'reachable'
            record(f'{src} to {dst}',code==0 and actual.get(dst)==expected,{'expected':expected,'actual':actual.get(dst),'stderr':err})
    for name,spec in NODES.items():
        if spec['role'] in ('router','mls'):
            out=scriptcheck(name,name+' OSPF command',"vtysh -c 'show ip ospf neighbor json'\nvtysh -c 'show ip route ospf'\n")
            record(name+' OSPF Full neighbor','Full' in out,out)
        if spec['role'] in ('mls','access1'):
            code,out,err=inside(name,'ovs-appctl lacp/show bond1\n')
            record(name+' two LACP members',code==0 and 'active negotiated' in out and out.count('may_enable: true')==2,{'stdout':out,'stderr':err})
        if spec['role']=='mls':
            code,out,err=inside(name,'nft -j list table inet fyp_policy\n')
            try:
                counters=[c['counter']['packets'] for obj in json.loads(out)['nftables'] if 'rule' in obj for c in obj['rule']['expr'] if 'counter' in c]
            except Exception:counters=[]
            record(name+' ACL deny counter',code==0 and any(c>0 for c in counters),{'stdout':out,'stderr':err})
    management=[(name,s['management_ip']) for name,s in NODES.items() if s.get('management_ip') and s['role']!='monitor']
    for name,ip in management:
        scriptcheck('MON-HQ','Management ping '+name,f'ping -c 1 -W 2 {ip}\n')
        code,out,err=inside('MON-HQ',f"source /etc/fyp/secrets.sh\nsnmpget -m '' -v2c -c \"$SNMP_COMMUNITY\" -t 2 -r 1 -Oqv {ip} 1.3.6.1.2.1.1.5.0\n")
        record('SNMP identity '+name,code==0 and name in out,{'stdout':out,'stderr':err})
        scriptcheck(name,'Emit syslog '+name,f"logger -t fyp-check '{syslog_marker} node={name}'\n")
    time.sleep(2)
    code,out,err=inside('MON-HQ',"grep '"+syslog_marker+" node=' /var/log/fyp/received-syslog.log\n")
    for name,ip in management:record('Central syslog '+name,code==0 and ('node='+name+'\n' in out or 'node='+name+' ' in out or out.rstrip().endswith('node='+name)),{'seen':name in out})
    ids=' '.join(shlex.quote(n['properties']['container_id']) for n in nodes.values())
    code,out,err=run('sudo -n docker stats --no-stream --format "{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}" '+ids)
    record('Resource snapshot',code==0,{'stdout':out,'stderr':err})
    code,out,err=run('free -m; df -h / /opt/gns3')
    record('Guest resource snapshot',code==0,{'stdout':out,'stderr':err})
finally:
    dest=ROOT/'docs/verification/network';dest.mkdir(parents=True,exist_ok=True)
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'project_id':pid,'passed':len(results)==243 and all(r['passed'] for r in results),'checks':len(results),'failures':sum(not r['passed'] for r in results),'results':results,'syslog_marker':syslog_marker}
    (dest/'verification.json').write_text(json.dumps(report,indent=2))
    client.close()
print(f'Checks: {len(results)}; failures: {report["failures"]}',flush=True)
raise SystemExit(0 if report['passed'] else 1)
