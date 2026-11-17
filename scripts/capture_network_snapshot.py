"""Read-only console snapshots, without intervention names or ground-truth labels."""
import json
import sys
import uuid
from datetime import datetime,timezone
from gns3_api import ROOT
from lab_runtime import Lab

def capture(lab,tolerate_errors=False):
    observations=[]
    for name,spec in lab.manifest['nodes'].items():
        if spec['role'] in ('host','monitor'):continue
        commands={'addresses':['ip','-j','address','show'],'routes':['ip','-j','route','show']}
        if spec['role'] in ('router','mls'):
            commands.update(ospf_neighbors=['vtysh','-c','show ip ospf neighbor json'],frr_configuration=['vtysh','-c','show running-config'])
        if spec['role']=='mls':commands['acl']=['nft','-j','list','table','inet','fyp_policy']
        if spec['role'] in ('mls','wan','access1','access2'):commands['switch_configuration']=['ovs-vsctl','show']
        script="python3 - <<'SNAPSHOT_PY'\nimport json,subprocess\nfrom datetime import datetime,timezone\nobserved_at=datetime.now(timezone.utc).isoformat()\ncommands="+repr(commands)+"\nresult={}\nfor name,args in commands.items():\n p=subprocess.run(args,capture_output=True,text=True,timeout=10)\n result[name]={'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}\nprint(json.dumps({'observed_at':observed_at,'raw':result}))\nSNAPSHOT_PY\n"
        try:
            _,out,_=lab.inside(name,script)
            payload=json.loads(out)
        except (RuntimeError,TypeError,KeyError,ValueError) as error:
            if not tolerate_errors:raise
            payload={'observed_at':datetime.now(timezone.utc).isoformat(),'raw':{'collection_error':{
              'exit_code':1,'stdout':'','stderr':'Read-only console snapshot unavailable',
              'error_type':type(error).__name__,'timestamp_source':'controller_utc'}}}
        observations.append({'snapshot_id':str(uuid.uuid4()),'device_id':name,'observed_at':payload['observed_at'],'raw':payload['raw']})
    return observations

if __name__=='__main__':
    lab=Lab();lab.load();lab.connect()
    try:
        rows=capture(lab)
        dest=ROOT/'docs/verification/telemetry';dest.mkdir(parents=True,exist_ok=True)
        target=dest/('snapshots-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.json')
        target.write_text(json.dumps(rows,indent=2))
        print(str(target));print('Read-only device snapshots:',len(rows))
        _,out,_=lab.run('date -u +%s; timedatectl show -p NTPSynchronized -p TimeUSec 2>/dev/null || true')
        (dest/'clock-check.json').write_text(json.dumps({'controller_epoch':datetime.now(timezone.utc).timestamp(),'guest_output':out},indent=2))
    finally:lab.close()
