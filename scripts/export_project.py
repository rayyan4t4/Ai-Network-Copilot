"""Export a quiescent project, then prove saved network and database startup."""
import concurrent.futures
import hashlib
import json
import shutil
import shlex
import tarfile
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from gns3_api import ROOT, api, api_request
from lab_runtime import Lab
from monitor_sql import query

lab=Lab();lab.load();lab.connect()
dest=ROOT/'docs/verification/reference';dest.mkdir(parents=True,exist_ok=True)
backup=ROOT/'.local/backups/current';backup.mkdir(parents=True,exist_ok=True)
checks=[];completed=False;resume=False
count_sql="""SELECT (SELECT count(*) FROM telemetry.polls) polls,
 (SELECT count(*) FROM telemetry.interface_samples) samples,
 (SELECT count(*) FROM telemetry.syslog_events) events,
 (SELECT count(*) FROM telemetry.config_snapshots) snapshots"""
try:
    lab.run('sudo -n install -d -o gns3 -g gns3 /opt/gns3/projects/fyp-backups')
    _,maintenance,_=lab.run('systemctl show apt-daily-upgrade.service -p ActiveState --value')
    if maintenance.strip() in ('activating','active','deactivating'):
        raise RuntimeError('Wait for the scheduled guest OS upgrade to finish before lifecycle testing')
    before=query(lab,count_sql)[0]
    anchor=query(lab,'SELECT poll_id::text FROM telemetry.polls ORDER BY observed_at LIMIT 1')[0]['poll_id']
    resume=True
    # Flush both collectors and PostgreSQL before GNS3 captures persistent volumes.
    lab.inside('MON-HQ','''kill -TERM "$(cat /run/copilot-supervisor.pid)"
pkill -TERM -f '^python3 -u /opt/copilot/collector.py run$' || true
for attempt in $(seq 1 60); do
 if ! pgrep -f '^python3 -u /opt/copilot/collector.py run' >/dev/null; then break; fi
 sleep 1
done
if pgrep -f '^python3 -u /opt/copilot/collector.py run' >/dev/null; then exit 1; fi
runuser -u postgres -- /usr/lib/postgresql/15/bin/pg_ctl -D /var/lib/postgresql/fyp/data -m fast -w stop
''')
    def stop(n):
        if n['status']=='started':api(f'/projects/{lab.pid}/nodes/{n["node_id"]}/stop','POST')
        return n['name']
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for name in pool.map(stop,list(lab.nodes.values())):print('Saved and stopped '+name,flush=True)
    deadline=time.monotonic()+15
    while True:
        lab.refresh()
        if all(n['status']=='stopped' for n in lab.nodes.values()):break
        if time.monotonic()>deadline:break
        time.sleep(1)
    assert len(lab.nodes)==30 and all(n['status']=='stopped' for n in lab.nodes.values())
    # Preserve every cleanly stopped guest file independently of the default
    # export's filters and permissions, then add omitted regular members.
    # In the verified run GNS3 included credentials/data but omitted .log files.
    guest='/opt/gns3/projects/fyp-backups/persistent-volumes.tgz'
    lab.run('sudo -n tar -czf '+shlex.quote(guest)+' -C '+shlex.quote('/opt/gns3/projects/'+lab.pid)+' project-files',timeout=300)
    lab.run('sudo -n chown gns3:gns3 '+shlex.quote(guest))
    private=backup/'persistent-volumes.tgz'
    s=lab.client.open_sftp();s.get(guest,str(private));s.close()
    _,remote_digest,_=lab.run('sha256sum '+shlex.quote(guest))
    with private.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==remote_digest.split()[0]
    path=backup/'AI Network Copilot.gns3project'
    request=api_request(f'/projects/{lab.pid}/export?include_images=no&keep_compute_ids=no')
    with urllib.request.urlopen(request,timeout=300) as response,path.open('wb') as output:
        shutil.copyfileobj(response,output)
    with tarfile.open(private,'r:gz') as source,zipfile.ZipFile(path,'a',compression=zipfile.ZIP_DEFLATED) as archive:
        known=set(archive.namelist());added=[]
        for member in source:
            if not member.isfile() or member.name in known:continue
            info=zipfile.ZipInfo(member.name,date_time=datetime.fromtimestamp(member.mtime,timezone.utc).timetuple()[:6])
            info.create_system=3;info.external_attr=(member.mode | 0o100000)<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            with source.extractfile(member) as stream:archive.writestr(info,stream.read())
            added.append(member.name)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        members=archive.namelist()
        assert any(p.endswith('.gns3') for p in members)
        assert any('PG_VERSION' in p for p in members)
        assert any('collector.py' in p for p in members)
        assert any(p.endswith('/etc/fyp/collector.json') for p in members)
        assert sum(p.endswith('/etc/fyp/secrets.sh') for p in members)==30
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    checks.append({'test':'Stopped project export contains topology, monitor source and PostgreSQL data','passed':True,
      'bytes':path.stat().st_size,'members':len(members),'sha256':digest,
      'images_included':False,'privileged_persistent_files_added':len(added),
      'private_volume_backup_bytes':private.stat().st_size})
    print('Portable project archive verified.',flush=True)
except Exception as error:
    (dest/'saved-startup-and-export.json').write_text(json.dumps({'recorded_at':datetime.now(timezone.utc).isoformat(),
      'passed':False,'checks':checks,'error':str(error)},indent=2))
    raise
finally:
    # Resume the actual lab even if export fails.
    if resume:lab.refresh();lab.start()

try:
    deadline=time.monotonic()+150
    while True:
        try:
            after=query(lab,count_sql)[0]
            rows=query(lab,"""SELECT
             (SELECT count(*) FROM telemetry.latest_polls WHERE status='ok' AND NOT is_stale) healthy_polls,
             (SELECT count(*) FROM telemetry.latest_probes WHERE status='ok' AND NOT is_stale) healthy_probes""")[0]
            if rows['healthy_polls']==17 and rows['healthy_probes']==29 and after['polls']>before['polls']:break
        except RuntimeError:pass
        if time.monotonic()>deadline:raise RuntimeError('Saved startup did not reach a healthy collection baseline')
        print('Waiting for saved startup and routing convergence...',flush=True);time.sleep(5)
    checks.append({'test':'Database observations persist across full 30-node stop/start','passed':all(after[k]>=v for k,v in before.items()),'before':before,'after':after})
    anchor_count=query(lab,'SELECT count(*) n FROM telemetry.polls WHERE poll_id=%s',[anchor])[0]['n']
    checks.append({'test':'Original observation identity survives restart','passed':anchor_count==1,'poll_id':anchor})
    checks.append({'test':'All remote targets and SNMP recover after full startup','passed':rows['healthy_polls']==17 and rows['healthy_probes']==29,'observed':rows})
    dup=query(lab,'SELECT count(*) n FROM (SELECT file_generation,byte_offset FROM telemetry.syslog_events GROUP BY 1,2 HAVING count(*)>1) d')[0]['n']
    checks.append({'test':'Persistent Syslog checkpoint avoids duplicate evidence after restart','passed':dup==0,'duplicates':dup})
    completed=True
finally:
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'passed':completed and all(c['passed'] for c in checks),'checks':checks}
    (dest/'saved-startup-and-export.json').write_text(json.dumps(report,indent=2))
    lab.close()
print(json.dumps(report,indent=2),flush=True)
raise SystemExit(0 if report['passed'] else 1)
