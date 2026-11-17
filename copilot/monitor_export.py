"""Run as copilot_reader: bounded, consistent, SELECT-only telemetry export."""
import json
import psycopg2
from psycopg2.extras import RealDictCursor

def export():
    conn=psycopg2.connect(dbname='copilot',user='copilot_reader',host='/run/postgresql',connect_timeout=5)
    conn.set_session(readonly=True,isolation_level='REPEATABLE READ')
    try:
        with conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='10s'")
            cur.execute('SELECT clock_timestamp() at');at=cur.fetchone()['at']
            def rows(sql,args=None):cur.execute(sql,args);return [dict(r) for r in cur.fetchall()]
            result={'schema_version':'copilot.1','as_of':at,'source':'postgresql_repeatable_read','devices':rows('SELECT * FROM inventory.devices ORDER BY device_id'),
              'links':rows('SELECT * FROM inventory.links ORDER BY link_id'),'interfaces':rows('SELECT * FROM inventory.interfaces ORDER BY interface_id')}
            result['polls']=rows('''SELECT DISTINCT ON (device_id) poll_id,device_id,observed_at,received_at,status,error,collector_version
              FROM telemetry.polls WHERE received_at<=%s AND observed_at<=%s ORDER BY device_id,observed_at DESC''',[at,at])
            result['samples']=rows('''SELECT * FROM (SELECT s.*,p.device_id,row_number() OVER(PARTITION BY s.interface_id ORDER BY s.observed_at DESC) rn
              FROM telemetry.interface_samples s JOIN telemetry.polls p USING(poll_id)
              WHERE s.observed_at<=%s AND p.received_at<=%s AND s.observed_at>%s-interval '6 minutes') x WHERE rn<=4''',[at,at,at])
            result['probes']=rows('''SELECT * FROM (SELECT p.*,row_number() OVER(PARTITION BY device_id ORDER BY observed_at DESC) rn
              FROM telemetry.probes p WHERE observed_at<=%s AND received_at<=%s AND observed_at>%s-interval '2 minutes') x WHERE rn<=8''',[at,at,at])
            result['events']=rows('''SELECT event_id,device_id,event_time,received_at,ingested_at,program,message,raw,identity_status,parse_error
              FROM telemetry.syslog_events WHERE received_at<=%s AND ingested_at<=%s AND received_at>%s-interval '5 minutes'
              AND program IN ('link-state','ospfd') ORDER BY received_at DESC LIMIT 200''',[at,at,at])
            result['snapshots']=rows('''SELECT * FROM (SELECT s.*,row_number() OVER(PARTITION BY device_id ORDER BY observed_at DESC) rn
              FROM telemetry.config_snapshots s WHERE observed_at<=%s AND received_at<=%s AND observed_at>%s-interval '6 minutes') x WHERE rn<=2''',[at,at,at])
            result['heartbeats']=rows('SELECT service,updated_at,status,detail FROM operations.heartbeats ORDER BY service')
            result['counts']=rows('''SELECT (SELECT count(*) FROM telemetry.polls) polls,
              (SELECT count(*) FROM telemetry.interface_samples) samples,(SELECT count(*) FROM telemetry.probes) probes,
              (SELECT count(*) FROM telemetry.syslog_events) events,(SELECT count(*) FROM telemetry.config_snapshots) snapshots''')[0]
            return result
    finally:conn.close()

if __name__=='__main__':print(json.dumps(export(),default=str,separators=(',',':')))
