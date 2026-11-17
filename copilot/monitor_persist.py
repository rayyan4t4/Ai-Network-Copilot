"""Trusted maintenance writer: incident JSON only; no SQL or shell from a model."""
import json
import sys
import psycopg2
from psycopg2.extras import Json

def persist(data):
    conn=psycopg2.connect(dbname='copilot',user='root',host='/run/postgresql')
    try:
        with conn,conn.cursor() as cur:
            for item in data.get('incidents',[])[:1000]:
                cur.execute('''INSERT INTO incidents.records VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                  ON CONFLICT(incident_id) DO UPDATE SET updated_at=excluded.updated_at,resolved_at=excluded.resolved_at,state=excluded.state,package=excluded.package''',
                  (item['incident_id'],item['fingerprint'],item['opened_at'],item['updated_at'],item.get('resolved_at'),item['state'],item['fault_class'],item['device_id'],item.get('interface'),Json(item)))
                cur.execute('INSERT INTO incidents.rules_applied VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                  (item['incident_id'],item['evidence_digest'],item['updated_at'],Json(item['rules_applied'])))
            for d in data.get('diagnoses',[])[:1000]:
                audit={k:d[k] for k in ('system_instruction','generation_settings','provider_response','prompt_version','test_kind','incident_to_result_ms') if k in d}
                cur.execute('''INSERT INTO incidents.diagnoses(diagnosis_id,incident_id,recorded_at,model,model_version,status,prompt_hash,request,response,validation,latency_ms,usage,evidence_package,audit)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                  (d['diagnosis_id'],d['incident_id'],d['recorded_at'],d.get('model'),d.get('model_version'),d['status'],d.get('prompt_hash'),Json(d.get('request',{})),Json(d.get('response',{})),Json(d.get('validation',{})),d.get('latency_ms'),Json(d.get('usage',{})),Json(d.get('evidence_package',{})),Json(audit)))
    finally:conn.close()

if __name__=='__main__':persist(json.load(sys.stdin));print('Incident records persisted.')
