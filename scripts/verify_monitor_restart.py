"""Cleanly restart only MON-HQ and check persistence of post-study maintenance."""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from lab_runtime import Lab
from gns3_api import api
from monitor_sql import query
from evaluation.freeze import verify


def main():
    verify()
    lab = Lab()
    lab.load()
    lab.connect()
    restart = False
    receipt = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'passed': False,
               'scope': 'MON-HQ clean stop/start only, after the completed frozen study. No fault trial or cloud request.'}
    try:
        before = query(lab, 'SELECT count(*) n FROM telemetry.polls')[0]['n']
        anchor = query(lab, 'SELECT poll_id::text id FROM telemetry.polls ORDER BY observed_at LIMIT 1')[0]['id']
        restart = True
        lab.inside('MON-HQ', '''kill -TERM "$(cat /run/copilot-supervisor.pid)"
pkill -TERM -f '^python3 -u /opt/copilot/collector.py run$' || true
for attempt in $(seq 1 60); do
 if ! pgrep -f '^python3 -u /opt/copilot/collector.py run' >/dev/null; then break; fi
 sleep 1
done
if pgrep -f '^python3 -u /opt/copilot/collector.py run' >/dev/null; then exit 1; fi
runuser -u postgres -- /usr/lib/postgresql/15/bin/pg_ctl -D /var/lib/postgresql/fyp/data -m fast -w stop
''')
        node = lab.nodes['MON-HQ']['node_id']
        api(f'/projects/{lab.pid}/nodes/{node}/stop', 'POST')
        api(f'/projects/{lab.pid}/nodes/{node}/start', 'POST')
        lab.refresh()
        deadline = time.monotonic() + 150
        while True:
            try:
                row = query(lab, """SELECT
                  (SELECT count(*) FROM telemetry.polls) polls,
                  (SELECT count(*) FROM telemetry.latest_polls WHERE status='ok' AND NOT is_stale) snmp,
                  (SELECT count(*) FROM telemetry.latest_probes WHERE status='ok' AND NOT is_stale) probes,
                  (SELECT count(*) FROM telemetry.polls WHERE poll_id=%s) anchor,
                  position('LATERAL' in pg_get_viewdef('telemetry.latest_probes'::regclass,true))>0 optimized""", [anchor])[0]
                if row['polls'] > before and row['snmp'] == 17 and row['probes'] == 29 and row['anchor'] == 1 and row['optimized']:
                    receipt.update(passed=True, polls_before=before, observed_after=row, original_poll_id=anchor)
                    break
            except RuntimeError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError('Monitor startup did not recover all expected checks within 150 seconds.')
            time.sleep(5)
        verify()
    finally:
        if restart:
            lab.refresh()
            if lab.nodes['MON-HQ']['status'] != 'started':
                api(f'/projects/{lab.pid}/nodes/{lab.nodes["MON-HQ"]["node_id"]}/start', 'POST')
        lab.close()
        (ROOT / 'docs/verification/live/monitor-startup.json').write_text(json.dumps(receipt, indent=2))
    print('Persistent monitor startup rehearsal passed:', receipt['observed_after'])


if __name__ == '__main__':
    main()
