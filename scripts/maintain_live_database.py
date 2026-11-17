"""Verify equivalent newest-row lookups, then apply a post-study view migration."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from evaluation.freeze import verify
from lab_runtime import Lab


def main():
    verify()
    lab = Lab()
    lab.load()
    lab.connect()
    try:
        migration = (ROOT / 'collector/migrations/20261117_live_latest_views.sql').read_text()
        script = '''python3 - <<'LIVE_DB'
import json,time,psycopg2
conn=psycopg2.connect(dbname='copilot',user='root',host='/run/postgresql',connect_timeout=5)
conn.set_session(isolation_level='REPEATABLE READ')
checks=[];definitions={}
try:
 with conn,conn.cursor() as cur:
  cur.execute("SET LOCAL statement_timeout='25s'")
  for table,key in [('polls','poll_id'),('probes','probe_id')]:
   view='telemetry.latest_'+table
   cur.execute('SELECT pg_get_viewdef(%s::regclass,true)',[view]);definitions[view]=cur.fetchone()[0]
   began=time.monotonic()
   cur.execute('SELECT '+key+'::text FROM '+view+' ORDER BY '+key)
   before=[r[0] for r in cur.fetchall()];old_ms=round((time.monotonic()-began)*1000,3)
   began=time.monotonic()
   cur.execute('SELECT p.'+key+'::text FROM inventory.devices d CROSS JOIN LATERAL (SELECT * FROM telemetry.'+table+' WHERE device_id=d.device_id ORDER BY observed_at DESC LIMIT 1) p ORDER BY p.'+key)
   after=[r[0] for r in cur.fetchall()];new_ms=round((time.monotonic()-began)*1000,3)
   assert before==after,(table,'Newest row identities differ; no migration applied')
   checks.append({'table':table,'same_row_ids':True,'rows':len(after),'before_query_ms':old_ms,'lateral_query_ms':new_ms})
  cur.execute(MIGRATION)
 print(json.dumps({'passed':True,'checks':checks,'original_view_definitions':definitions}))
finally:conn.close()
LIVE_DB
'''.replace('cur.execute(MIGRATION)', 'cur.execute(' + repr(migration) + ')')
        _, output, _ = lab.inside('MON-HQ', script, timeout=80)
        receipt = json.loads(output)
        receipt.update(recorded_at=datetime.now(timezone.utc).isoformat(),
                       migration_sha256=hashlib.sha256(migration.encode()).hexdigest(),
                       scope='Post-study live view optimization only. Same newest row IDs verified within one repeatable-read transaction before DDL. No stored data, frozen source, final output or reported timing changed.')
        target = ROOT / 'docs/verification/live/live-database-maintenance.json'
        target.write_text(json.dumps(receipt, indent=2))
        print('Live latest-row migration passed:', receipt['checks'])
    finally:
        lab.close()


if __name__ == '__main__':
    main()
