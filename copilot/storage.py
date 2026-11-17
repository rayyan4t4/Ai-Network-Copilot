"""Local request/response journal, budget and queue; no lab credentials."""
import json
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

def connect(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(str(directory/'diagnoses.sqlite3'),timeout=10)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY,incident_id TEXT NOT NULL,
      requested_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'queued',auto INTEGER NOT NULL);
      CREATE UNIQUE INDEX IF NOT EXISTS active_job ON jobs(incident_id) WHERE status IN ('queued','running');
      CREATE TABLE IF NOT EXISTS outputs(diagnosis_id TEXT PRIMARY KEY,incident_id TEXT NOT NULL,recorded_at TEXT NOT NULL,payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS calls(id INTEGER PRIMARY KEY,at TEXT NOT NULL,incident_id TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);''')
    return c

def outputs(directory):
    with connect(directory) as c:
        return [json.loads(r['payload']) for r in c.execute('SELECT payload FROM outputs ORDER BY recorded_at DESC LIMIT 1000')]

def enqueue(directory,incident_id,auto=False):
    with connect(directory) as c:
        try:
            c.execute('INSERT INTO jobs(incident_id,requested_at,auto) VALUES(?,?,?)',(incident_id,datetime.now(timezone.utc).isoformat(),int(auto)))
            return True
        except sqlite3.IntegrityError:return False

def save(directory,record):
    with connect(directory) as c:c.execute('INSERT INTO outputs VALUES(?,?,?,?) ON CONFLICT DO NOTHING',
      (record['diagnosis_id'],record['incident_id'],record['recorded_at'],json.dumps(record)))
