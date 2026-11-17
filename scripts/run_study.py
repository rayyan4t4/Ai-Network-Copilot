"""Real, checkpointed GNS3 injections. Ground truth never enters diagnoses."""
import argparse,copy,json,random,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from lab_runtime import Lab
from evaluation.protocol import CLASSES,mask,packet
P=json.loads((ROOT/'evaluation/profile.json').read_text())
CONTROL=ROOT/'.local/evaluation/control';OUT=ROOT/'research'
def now():return datetime.now(timezone.utc).isoformat()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,default=str));tmp.replace(path)
def bundle():return json.loads((ROOT/'.local/runtime/evidence.json').read_text())
def schedule(pilot=False):
    rng=random.Random(20261117);rows=[]
    categories=CLASSES+['healthy','insufficient']
    for category in categories:
        for n in range(1 if pilot else 10):
            kind=CLASSES[n%5] if category=='insufficient' else category
            branch='B'+str(n%3+1);device=('PC-'+branch+'-IT') if kind=='unreachability' else ('MLS-'+branch if kind=='acl_fault' else 'R-'+branch)
            rows.append({'case_id':str(uuid.UUID(int=rng.getrandbits(128))),'category':category,'underlying_class':kind,'branch':branch,'device_id':device if kind!='healthy' else '',
              'interface':'eth0' if kind in ('interface_shutdown','ospf_loss') else 'eth1' if kind=='high_utilization' else '',
              'target_host':'PC-'+branch+'-IT','load_mbps':3+n%2})
    rng.shuffle(rows)
    for i,r in enumerate(rows):r['sequence']=i+1
    return rows
def change(lab,row,restore=False):
    kind=row['underlying_class'];dev=row['device_id'];branch=row['branch']
    if kind=='interface_shutdown':script='ip link set eth0 '+('up' if restore else 'down')
    elif kind=='ospf_loss':script="vtysh -c 'configure terminal' -c 'interface eth0' -c '"+('no ' if restore else '')+"ip ospf passive'"
    elif kind=='unreachability':script='sysctl -qw net.ipv4.icmp_echo_ignore_all='+('0' if restore else '1')
    elif kind=='high_utilization':
        if restore:script='if test -f /run/fyp-study-client.pid; then kill $(cat /run/fyp-study-client.pid) 2>/dev/null || true; rm -f /run/fyp-study-client.pid; fi'
        else:script=f'nohup iperf3 -c 10.0.0.1 -u -b {row["load_mbps"]}M -t 180 >/tmp/fyp-study-traffic.log 2>&1 </dev/null & echo $! >/run/fyp-study-client.pid'
    elif kind=='acl_fault':
        ip=next(d['management_ip'] for d in bundle()['devices'] if d['device_id']==row['target_host'])
        if restore:
            script="nft -a list chain inet fyp_policy forward | sed -n '/comment \"study-owned\"/s/.*# handle //p' | while read h; do nft delete rule inet fyp_policy forward handle \"$h\"; done"
        else:script=f'nft add rule inet fyp_policy forward ip saddr 192.168.30.10 ip daddr {ip} counter drop comment \'study-owned\''
    elif kind=='healthy':return {'exit_code':0,'at':now()}
    else:raise ValueError(kind)
    code,out,err=lab.inside(dev,script+'\n',check=False)
    return {'exit_code':code,'at':now(),'stdout':out,'stderr':err}
def healthy():
    s=json.loads((ROOT/'.local/runtime/state.json').read_text())
    return len(s.get('health',[]))==30 and all(d['state']=='healthy' for d in s['health']) and (datetime.now(timezone.utc)-datetime.fromisoformat(s['as_of'])).total_seconds()<25
def wait_restore(start):
    while time.monotonic()-start<P['restore_timeout_seconds']:
        if time.monotonic()-start>=P['restore_minimum_seconds'] and healthy():return True
        time.sleep(3)
    return False
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pilot',action='store_true');ap.add_argument('--prepare',action='store_true');args=ap.parse_args()
    phase='pilot' if args.pilot else 'final';path=CONTROL/(phase+'-schedule.json')
    if not path.exists():save(path,schedule(args.pilot))
    if args.prepare:print('Prepared',path);return
    if not args.pilot:
        from evaluation.freeze import verify
        verify()
    lab=Lab();lab.load();lab.connect()
    try:
        for row in json.loads(path.read_text()):
            if not args.pilot:verify()
            case=OUT/phase/row['case_id'];record=CONTROL/phase/(row['case_id']+'.json')
            if record.exists() and json.loads(record.read_text()).get('complete'):continue
            if record.exists():
                previous=record.with_suffix('.attempts.json');history=json.loads(previous.read_text()) if previous.exists() else [];history.append(json.loads(record.read_text()));save(previous,history)
            if not wait_restore(time.monotonic()):raise RuntimeError('Healthy baseline not restored; refusing next injection')
            case.mkdir(parents=True,exist_ok=True);trial=dict(row,started_at=now(),complete=False)
            save(record,trial);print(phase,row['sequence'],row['category'],row['case_id'],flush=True)
            try:
                trial['intervention']=change(lab,row)
                if trial['intervention']['exit_code']:raise RuntimeError('Injection failed: '+str(trial['intervention']))
                time.sleep(P['capture_seconds'][row['underlying_class']])
                observed=bundle();save(case/'original.json',observed)
                observed=mask(observed,row['underlying_class']) if row['category']=='insufficient' else observed
                save(case/'observations.json',observed)
                p=packet(observed);save(case/'analysis.json',p)
                trial['captured_at']=now();trial['observed_as_of']=observed['as_of'];trial['capture_lag_seconds']=(datetime.now(timezone.utc)-datetime.fromisoformat(observed['as_of'])).total_seconds()
                trial['observed_candidates']=[{'class':c['fault_class'],'device':c['device_id'],'gate':c['gate']['status'],'missing':c['gate']['missing']} for c in __import__('evaluation.engine',fromlist=['analyze']).analyze(observed)['incidents']]
            finally:
                trial['restoration']=change(lab,row,True);trial['restored_at']=now();save(record,trial)
            trial['restoration_verified']=wait_restore(time.monotonic())
            trial['complete']=trial['restoration']['exit_code']==0 and trial['restoration_verified'];save(record,trial)
            print('captured',trial['observed_candidates'],'restored',trial['restoration_verified'],flush=True)
            if not trial['complete']:raise RuntimeError('Restoration failed')
    finally:lab.close()
if __name__=='__main__':main()
