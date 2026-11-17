"""Restore-test all application tables with application writers paused."""
import json
import uuid
from datetime import datetime,timezone
from gns3_api import ROOT
from lab_runtime import Lab
from monitor_sql import query

TABLES=['inventory.devices','inventory.links','inventory.interfaces','telemetry.polls','telemetry.interface_samples',
 'telemetry.device_health','telemetry.probes','telemetry.syslog_events','telemetry.config_snapshots',
 'operations.checkpoints','operations.heartbeats','incidents.records','incidents.diagnoses','incidents.rules_applied']
lab=Lab();lab.load();lab.connect();created=False;restart=False;passed=False
temp='copilot_restore_'+uuid.uuid4().hex[:10]
def counts(database='copilot'):
    return {t:query(lab,'SELECT count(*) n FROM '+t,database_name=database)[0]['n'] for t in TABLES}
try:
    (ROOT/'docs/verification/reference').mkdir(parents=True,exist_ok=True)
    lab.run('sudo -n install -d -o gns3 -g gns3 /opt/gns3/projects/fyp-backups')
    restart=True
    lab.inside('MON-HQ','''kill -TERM "$(cat /run/copilot-supervisor.pid)"
# Bash can defer a trap while waiting for its child. Signal the collector too.
pkill -TERM -f '^python3 -u /opt/copilot/collector.py run$' || true
for attempt in $(seq 1 60); do
 if ! pgrep -f '^python3 -u /opt/copilot/collector.py run' >/dev/null; then break; fi
 sleep 1
done
if pgrep -f '^python3 -u /opt/copilot/collector.py run' >/dev/null; then exit 1; fi
''')
    before=counts()
    lab.inside('MON-HQ','pg_dump -Fc -h /run/postgresql -U root -d copilot -f /var/log/fyp/database.dump\n')
    lab.inside('MON-HQ',f'runuser -u postgres -- createdb -h /run/postgresql -O root {temp}\n');created=True
    lab.inside('MON-HQ',f'pg_restore --single-transaction --exit-on-error --no-owner --no-acl -h /run/postgresql -U root -d {temp} /var/log/fyp/database.dump\n')
    restored=counts(temp);assert before==restored,(before,restored)
    guest='/opt/gns3/projects/fyp-backups/database.dump'
    cid=lab.nodes['MON-HQ']['properties']['container_id']
    lab.run('sudo -n docker cp '+cid+':/gns3volumes/var/log/fyp/database.dump '+guest)
    lab.run('sudo -n chown gns3:gns3 '+guest)
    directory=ROOT/'.local/backups/current';directory.mkdir(parents=True,exist_ok=True)
    s=lab.client.open_sftp();s.get(guest,str(directory/'database.dump'));s.close()
    passed=True
finally:
    if created:lab.inside('MON-HQ',f'runuser -u postgres -- dropdb -h /run/postgresql {temp}\n')
    if restart:lab.inside('MON-HQ','/bin/bash /opt/copilot/start.sh\n')
    lab.close()
report={'recorded_at':datetime.now(timezone.utc).isoformat(),'passed':passed,'source':before,'restored':restored,'tables':len(TABLES)}
(ROOT/'docs/verification/reference/database-restore.json').write_text(json.dumps(report,indent=2))
print('Restored all',len(TABLES),'application table counts exactly.',flush=True)
