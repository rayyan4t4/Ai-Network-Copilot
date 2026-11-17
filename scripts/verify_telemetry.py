import json
import time
import uuid
from datetime import datetime,timezone
from gns3_api import ROOT
from lab_runtime import Lab
from monitor_sql import query

lab=Lab();lab.load();lab.connect();checks=[];completed=False
marker='WEEK1_CONNECTIVITY_CHECK_'+uuid.uuid4().hex
def check(name,passed,details):
    checks.append({'test':name,'passed':bool(passed),'details':details})
    print(('PASS ' if passed else 'FAIL ')+name,flush=True)
try:
    deadline=time.monotonic()+110
    while True:
        counts=query(lab,"SELECT count(*) n FROM telemetry.latest_polls WHERE status='ok' AND NOT is_stale")
        rates=query(lab,"SELECT count(*) n FROM telemetry.interface_samples WHERE rate_status='valid' AND in_bps IS NOT NULL")
        if counts[0]['n']==17 and rates[0]['n']>0:break
        if time.monotonic()>deadline:break
        print('Waiting for two complete SNMP cycles...',flush=True);time.sleep(5)
    rows=query(lab,"SELECT (SELECT count(*) FROM inventory.devices) devices,(SELECT count(*) FROM inventory.links) links,(SELECT count(*) FROM inventory.interfaces) interfaces")
    check('Inventory has 30 devices and 33 links',rows[0]['devices']==30 and rows[0]['links']==33,rows)
    rows=query(lab,"SELECT device_id,status,is_stale,observed_at FROM telemetry.latest_polls ORDER BY device_id")
    check('All 17 latest SNMP polls are current and successful',len(rows)==17 and all(r['status']=='ok' and not r['is_stale'] for r in rows),rows)
    rows=query(lab,"SELECT device_id,status,is_stale,observed_at FROM telemetry.latest_probes ORDER BY device_id")
    check('All 29 target probes are current and successful',len(rows)==29 and all(r['status']=='ok' and not r['is_stale'] for r in rows),rows)
    rows=query(lab,"SELECT d.site,count(DISTINCT p.device_id) devices FROM telemetry.polls p JOIN inventory.devices d USING(device_id) WHERE p.status='ok' AND p.raw<>'{}'::jsonb GROUP BY d.site ORDER BY d.site")
    check('Raw SNMP evidence covers HQ three branches and WAN',{'HQ','B1','B2','B3','WAN'}.issubset({r['site'] for r in rows}),rows)
    rows=query(lab,"SELECT count(*) n FROM telemetry.interface_samples WHERE in_bps IS NOT NULL AND out_bps IS NOT NULL AND rate_status='valid'")
    check('Counter derived rates have valid intervals',rows[0]['n']>0,rows)
    rows=query(lab,"SELECT count(DISTINCT p.device_id) n FROM telemetry.device_health h JOIN telemetry.polls p USING(poll_id) WHERE h.sysuptime_ticks IS NOT NULL")
    check('SNMP agent uptime evidence exists for 17 devices',rows[0]['n']==17,rows)
    for name,spec in lab.manifest['nodes'].items():
        if spec['role'] not in ('host','monitor'):
            lab.inside(name,"logger -t copilot-check '"+marker+"'\n")
    deadline=time.monotonic()+25
    while True:
        rows=query(lab,"SELECT count(DISTINCT device_id) n FROM telemetry.syslog_events WHERE message LIKE %s",['%'+marker+'%'])
        if rows[0]['n']==17 or time.monotonic()>deadline:break
        time.sleep(2)
    check('Syslog stored from all 17 network devices',rows[0]['n']==17,rows)
    rows=query(lab,"SELECT identity_status,count(*) n FROM telemetry.syslog_events GROUP BY identity_status")
    check('Syslog source identities are recorded',any(r['identity_status']=='source_and_hostname' for r in rows),rows)
    rows=query(lab,"SELECT service,status,clock_timestamp()-updated_at<interval '45 seconds' fresh,detail FROM operations.heartbeats ORDER BY service")
    check('All three collector services have fresh heartbeats',len(rows)==3 and all(r['status']=='ok' and r['fresh'] for r in rows),rows)
    rows=query(lab,"SELECT count(*) n FROM telemetry.polls WHERE received_at>=observed_at")
    check('Observation and ingestion times are distinct stored fields',rows[0]['n']>0,rows)
    rows=query(lab,"SELECT count(*) n FROM telemetry.config_snapshots")
    check('Read only configuration snapshots stored',rows[0]['n']>=17,rows)
    _,out,_=lab.inside('MON-HQ',"python3 /opt/copilot/collector.py status\n")
    status=json.loads(out)
    dest=ROOT/'docs/verification/telemetry';dest.mkdir(parents=True,exist_ok=True)
    (dest/'telemetry-status.json').write_text(json.dumps(status,indent=2))
    completed=True
finally:
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'passed':completed and all(c['passed'] for c in checks),'checks':checks,'syslog_marker':marker}
    dest=ROOT/'docs/verification/telemetry';dest.mkdir(parents=True,exist_ok=True)
    (dest/'telemetry-verification.json').write_text(json.dumps(report,indent=2))
    lab.close()
raise SystemExit(0 if report['passed'] else 1)
