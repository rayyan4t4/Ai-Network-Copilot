import json
import sys
from pathlib import Path
from psycopg2.extras import Json
from collector import database
rows=json.loads(Path(sys.argv[1]).read_text())
with database() as connection,connection.cursor() as cursor:
    for row in rows:
        cursor.execute('INSERT INTO telemetry.config_snapshots(snapshot_id,device_id,observed_at,raw) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',
          (row['snapshot_id'],row['device_id'],row['observed_at'],Json(row['raw'])))
print('Imported snapshots:',len(rows))
