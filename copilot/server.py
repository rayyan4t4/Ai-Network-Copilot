"""Loopback dashboard and Gemini worker. No GNS3/SSH imports or command executor."""
import argparse
import json
import logging
import re
import sys
import threading
import time
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from copilot import storage
from copilot.provider import diagnose
from evaluation.service import save_feedback
from live.provider import diagnose_live

DATA=ROOT/'.local/runtime';KEY=ROOT/'.local/gemini-key.txt';WEB=ROOT/'copilot/web'
MODEL='gemini-3.5-flash-lite';DAILY_LIMIT=6

def provider_approved():
    p=DATA/'provider-consent.json'
    return p.exists() and json.loads(p.read_text()).get('normalized_incident_summaries_to_google') is True

def evaluation_active():
    p=DATA/'evaluation-active.json'
    return p.exists() and json.loads(p.read_text()).get('active') is True

def current():
    path=DATA/'state.json'
    if not path.exists():return {'bridge':{'status':'starting'},'incidents':[],'health':[],'facts':[]}
    state=json.loads(path.read_text(encoding='utf-8'))
    try:age=(datetime.now(timezone.utc)-datetime.fromisoformat(state['as_of'])).total_seconds()
    except (ValueError,KeyError):age=9999
    state['observation_age_seconds']=round(age,1);state['is_stale']=age>45 or age< -5
    if state['is_stale'] or state.get('bridge',{}).get('status')!='ok':
        state['health']=[dict(d,state='unknown') for d in state.get('health',[])]
    state['diagnoses']=storage.outputs(DATA)
    state['replays']=['insufficient'] if (ROOT/'research/replays/insufficient.json').exists() else []
    state['provider']={'model':MODEL,'daily_request_limit':DAILY_LIMIT,'key_configured':KEY.exists(),
      'automatic_diagnosis':'paused for controlled evaluation' if evaluation_active() else 'once per sufficient incident','billing_settings_changed':False,'external_summaries_approved':provider_approved()}
    ledger=ROOT/'.local/evaluation/control/model-attempts.json'
    state['provider']['study_attempts']=len(json.loads(ledger.read_text())) if ledger.exists() else 0
    profile_path=ROOT/'evaluation/profile.json'
    state['provider']['study_attempt_cap']=json.loads(profile_path.read_text())['maximum_study_generation_attempts'] if profile_path.exists() else 260
    with storage.connect(DATA) as c:
        state['provider']['calls_today']=c.execute('SELECT count(*) FROM calls WHERE substr(at,1,10)=?',(datetime.now(timezone.utc).date().isoformat(),)).fetchone()[0]
    return state

def ai_loop():
    # A crash cannot silently leave a job in running state forever.
    with storage.connect(DATA) as c:c.execute("UPDATE jobs SET status='interrupted' WHERE status='running'")
    while True:
        try:
            state=current();existing={d['incident_id'] for d in state.get('diagnoses',[])}
            if not evaluation_active() and provider_approved() and not state.get('is_stale',True) and state.get('bridge',{}).get('status')=='ok':
                for item in state.get('incidents',[]):
                    if item['state']!='resolved' and item['gate']['status']=='sufficient' and item['incident_id'] not in existing:
                        storage.enqueue(DATA,item['incident_id'],auto=True)
            with storage.connect(DATA) as c:
                c.execute('BEGIN IMMEDIATE')
                job=c.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
                if job:c.execute("UPDATE jobs SET status='running' WHERE id=?",(job['id'],))
            if not job:time.sleep(2);continue
            state=current();item=next((i for i in state['incidents'] if i['incident_id']==job['incident_id']),None)
            if item is None or item['state']=='resolved' or state.get('is_stale',True) or state.get('bridge',{}).get('status')!='ok':
                with storage.connect(DATA) as c:c.execute("UPDATE jobs SET status='cancelled_stale' WHERE id=?",(job['id'],))
                continue
            allowed=True
            if item['gate']['status']=='sufficient' and provider_approved():
                now=datetime.now(timezone.utc)
                with storage.connect(DATA) as c:
                    c.execute('BEGIN IMMEDIATE')
                    count=c.execute('SELECT count(*) FROM calls WHERE substr(at,1,10)=?',(now.date().isoformat(),)).fetchone()[0]
                    cooldown=c.execute("SELECT value FROM settings WHERE key='cooldown_until'").fetchone()
                    allowed=count<DAILY_LIMIT and (not cooldown or float(cooldown[0])<time.time())
                    if allowed:c.execute('INSERT INTO calls(at,incident_id) VALUES(?,?)',(now.isoformat(),item['incident_id']))
            if not allowed:
                with storage.connect(DATA) as c:c.execute("UPDATE jobs SET status='budget_or_cooldown' WHERE id=?",(job['id'],))
                # Record the withheld attempt so automatic queuing does not loop.
                record={'diagnosis_id':__import__('uuid').uuid4().hex,'incident_id':item['incident_id'],
                  'recorded_at':datetime.now(timezone.utc).isoformat(),'status':'budget_or_cooldown','model':MODEL,
                  'response':{'reason':'Daily request cap or provider cooldown; no model request made.'},'validation':{'valid':False,'model_called':False}}
            elif item.get('gate',{}).get('matrix_version','').startswith('study-'):
                record=diagnose_live(item,json.loads((DATA/'evidence.json').read_text()))
            else:record=diagnose(item,KEY,model=MODEL)
            storage.save(DATA,record)
            if record['status']=='provider_error':
                with storage.connect(DATA) as c:c.execute("INSERT OR REPLACE INTO settings VALUES('cooldown_until',?)",(str(time.time()+900),))
            with storage.connect(DATA) as c:c.execute("UPDATE jobs SET status='done' WHERE id=?",(job['id'],))
        except Exception as error:
            logging.error('Diagnosis worker failed: %s',type(error).__name__)
        time.sleep(2)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,data,mime='application/json'):
        body=json.dumps(data,default=str).encode() if mime=='application/json' else data
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)
    def valid_host(self):return self.headers.get('Host','') in ('127.0.0.1:8765','localhost:8765')
    def do_GET(self):
        if not self.valid_host():self.reply(403,{'error':'Invalid host'});return
        if self.path=='/api/state':self.reply(200,current());return
        if self.path=='/api/replay/insufficient':
            p=ROOT/'research/replays/insufficient.json'
            if p.exists():self.reply(200,json.loads(p.read_text()));return
            self.reply(404,{'error':'Replay not recorded yet'});return
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','application/javascript'),'/style.css':('style.css','text/css')}
        if self.path not in files:self.reply(404,{'error':'Not found'});return
        name,mime=files[self.path];self.reply(200,(WEB/name).read_bytes(),mime)
    def do_POST(self):
        origins=('http://127.0.0.1:8765','http://localhost:8765')
        if not self.valid_host() or self.headers.get('Origin') not in origins or self.headers.get('X-Copilot-Action')!='diagnose':
            self.reply(403,{'error':'Same-origin dashboard request required'});return
        if self.path not in ('/api/diagnose','/api/feedback'):self.reply(404,{'error':'No configuration or command-execution endpoints'});return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<=0 or size>8192 or self.headers.get('Content-Type')!='application/json':raise ValueError()
            data=json.loads(self.rfile.read(size))
            if self.path=='/api/feedback':
                self.reply(201,save_feedback(data,{i['incident_id'] for i in current()['incidents']}));return
            if set(data)!= {'incident_id'} or not re.fullmatch(r'[a-f0-9\-]{36}',data['incident_id']):raise ValueError()
            state=current();item=next((i for i in state['incidents'] if i['incident_id']==data['incident_id']),None)
            if not item or item['state']=='resolved' or state.get('is_stale',True):self.reply(409,{'error':'Incident unavailable, resolved or stale'});return
            queued=storage.enqueue(DATA,item['incident_id']);self.reply(202,{'queued':queued})
        except (ValueError,TypeError,KeyError):self.reply(400,{'error':'Expected a valid incident identifier only'})

def main():
    parser=argparse.ArgumentParser();parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
    threading.Thread(target=ai_loop,daemon=True).start()
    print('Dashboard: http://127.0.0.1:8765',flush=True)
    server.serve_forever()

if __name__=='__main__':main()
