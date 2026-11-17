"""SQL over the existing control channel; database remains local to MON-HQ."""
import json

def query(lab,sql,parameters=None,database_name='copilot'):
    script="""python3 - <<'COPILOT_SQL'
import json,psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname=DATABASE_NAME,user='root',host='/run/postgresql')
try:
 with conn,conn.cursor(cursor_factory=RealDictCursor) as cursor:
  cursor.execute(SQL,PARAMETERS)
  rows=cursor.fetchall() if cursor.description else []
  print(json.dumps(rows,default=str))
finally:conn.close()
COPILOT_SQL
""".replace('SQL,PARAMETERS',repr(sql)+','+repr(parameters)).replace('DATABASE_NAME',repr(database_name))
    _,out,_=lab.inside('MON-HQ',script)
    return json.loads(out)
