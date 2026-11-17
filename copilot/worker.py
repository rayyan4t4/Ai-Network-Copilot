"""Trusted fixed-command lab bridge, separate from the diagnostic web process."""
import argparse
import json
import logging
import sys
import time
import uuid
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from lab_runtime import Lab
from capture_network_snapshot import capture
from copilot.engine import analyze,dt,digest
from copilot.storage import outputs

STATE=ROOT/'.local/runtime';STATE.mkdir(parents=True,exist_ok=True)

def atomic(path,value):
    p=Path(path);temporary=p.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,default=str),encoding='utf-8')
    for attempt in range(10):
        try:temporary.replace(p);return
        except PermissionError:time.sleep(.05)
    raise RuntimeError('Could not replace state file')

def recovered(incident,result):
    facts=[f for f in result['facts'] if not f['is_stale'] and f['device_id']==incident['device_id']]
    health={d['device_id']:d['state'] for d in result['health']}
    kind=incident['fault_class'];ident=incident['device_id']+':'+(incident.get('interface') or '')
    if kind=='interface_shutdown':
        snmp=any(f['kind']=='interface' and f['value']['interface_id']==ident and f['value']['admin_status']==1 and f['value']['oper_status']==1 for f in facts)
        console=any(f['kind']=='console_interface' and f['value']['interface']==incident['interface'] and f['value']['admin_up'] for f in facts)
        return snmp and console and all(health.get(d)=='healthy' for d in incident['affected_devices'])
    if kind=='unreachability':return health.get(incident['device_id'])=='healthy'
    if kind=='ospf_loss':
        return health.get(incident['device_id'])=='healthy' and any(f['kind']=='ospf_neighbors' and any('Full' in n.get('state','') and
          (n.get('address') in incident.get('expected_neighbors',[]) or n.get('ifaceName','').split(':')[0]==incident['interface'])
          for v in f['value'].get('neighbors',{}).values() for n in v) for f in facts)
    if kind=='acl_fault':return all(health.get(d)=='healthy' for d in incident['affected_devices'])
    if kind=='high_utilization':
        return any(f['kind']=='interface' and f['value']['interface_id']==ident and f['value']['rate_status']=='valid' and max(f['value'].get('in_utilization_pct') or 0,f['value'].get('out_utilization_pct') or 0)<70 for f in facts)
    return False

def update_lifecycle(result,old):
    records={i['incident_id']:i for i in old};active={i['fingerprint']:i for i in old if i['state']!='resolved'};present=set()
    for c in result['incidents']:
        fingerprint=c['fingerprint'];present.add(fingerprint)
        previous=active.get(fingerprint)
        c.update(incident_id=previous['incident_id'] if previous else str(uuid.uuid4()),
          opened_at=previous['opened_at'] if previous else result['as_of'],updated_at=result['as_of'],
          state='active' if c['gate']['status']=='sufficient' else 'inconclusive',resolved_at=None)
        c['created_at_controller']=previous.get('created_at_controller',datetime.now(timezone.utc).isoformat()) if previous else datetime.now(timezone.utc).isoformat()
        if previous:c['affected_devices']=sorted(set(c['affected_devices'])|set(previous['affected_devices']))
        records[c['incident_id']]=c
    for fingerprint,item in active.items():
        if fingerprint in present:continue
        if recovered(item,result):
            item=dict(item,state='resolved',resolved_at=result['as_of'],updated_at=result['as_of'])
            item['resolution_basis']='Positive fresh recovery observations and expected probes; absence of alerts alone was not used.'
        else:
            item=dict(item,state='inconclusive',updated_at=result['as_of'])
            item['gate']=dict(item['gate'],status='inconclusive',missing_critical=['fresh_distinguishing_evidence'],
              contradictions=[],historical_evidence=True)
        records[item['incident_id']]=item
    return sorted(records.values(),key=lambda i:i['opened_at'],reverse=True)[:1000]

def cycle(lab,last_snapshot=0):
    settings_path=STATE/'runtime-settings.json'
    settings=json.loads(settings_path.read_text()) if settings_path.exists() else {}
    snapshot_interval=settings.get('snapshot_interval_seconds',45)
    if time.monotonic()-last_snapshot>=snapshot_interval:
        observations=capture(lab,tolerate_errors=True)
        lab.upload_node('MON-HQ','/opt/copilot/app-snapshots.json',json.dumps(observations))
        lab.inside('MON-HQ','python3 /opt/copilot/import_snapshots.py /opt/copilot/app-snapshots.json\n')
        last_snapshot=time.monotonic()
    _,text,_=lab.inside('MON-HQ','runuser -u copilot_reader -- python3 /opt/copilot/app/monitor_export.py\n')
    bundle=json.loads(text);atomic(STATE/'evidence.json',bundle)
    if settings.get('engine')=='evaluation':
        from evaluation.engine import analyze as study_analyze
        result=study_analyze(bundle)
    else:result=analyze(bundle)
    previous=json.loads((STATE/'state.json').read_text(encoding='utf-8')).get('incidents',[]) if (STATE/'state.json').exists() else []
    result['incidents']=update_lifecycle(result,previous)
    result['bridge']={'status':'ok','updated_at':datetime.now(timezone.utc).isoformat(),'snapshot_interval_seconds':snapshot_interval,'export_interval_seconds':settings.get('export_interval_seconds',10)}
    atomic(STATE/'state.json',result)
    records={'incidents':result['incidents'],'diagnoses':outputs(STATE)}
    script="python3 - <<'PERSIST'\nimport sys\nsys.path.insert(0,'/opt/copilot/app')\nfrom monitor_persist import persist\nimport json\npersist(json.loads("+repr(json.dumps(records))+"))\nPERSIST\n"
    lab.inside('MON-HQ',script)
    print(json.dumps({'at':result['as_of'],'active_incidents':sum(i['state']!='resolved' for i in result['incidents']),
      'healthy_devices':sum(d['state']=='healthy' for d in result['health'])}),flush=True)
    return last_snapshot

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    last=0
    while True:
        lab=Lab()
        try:
            lab.load();lab.connect();last=cycle(lab,last)
        except Exception as error:
            # Credentials and arbitrary subprocess output never enter browser state.
            logging.error('Bridge cycle failed: %s',type(error).__name__)
            if (STATE/'state.json').exists():
                state=json.loads((STATE/'state.json').read_text(encoding='utf-8'))
                state['bridge']={'status':'error','updated_at':datetime.now(timezone.utc).isoformat(),'error':'Lab export unavailable; displayed observations may be stale.'}
                atomic(STATE/'state.json',state)
            if args.once:raise
        finally:lab.close()
        if args.once:break
        settings_path=STATE/'runtime-settings.json'
        settings=json.loads(settings_path.read_text()) if settings_path.exists() else {}
        time.sleep(settings.get('export_interval_seconds',10))

if __name__=='__main__':main()
