"""Loopback study viewer, browser display acknowledgements and human feedback."""
import json,sqlite3,sys,time,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];WEB=ROOT/'evaluation/web'
DB=ROOT/'.local/evaluation/reviews.sqlite3'
@contextmanager
def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=10);c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS display_ack(result_id TEXT PRIMARY KEY, at TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY, at TEXT NOT NULL, target_id TEXT NOT NULL, reviewer TEXT NOT NULL, decision TEXT NOT NULL, correction TEXT NOT NULL, usefulness INTEGER NOT NULL, supported INTEGER NOT NULL, notes TEXT NOT NULL)')
    try:
        yield c;c.commit()
    except Exception:
        c.rollback();raise
    finally:c.close()
def results():
    rows=[]
    for phase in ('pilot','final'):
        for p in (ROOT/'research'/phase).glob('*/*.json'):
            if p.stem not in ('B1','B2','no_gate','full'):continue
            r=json.loads(p.read_text());r.pop('provider_response',None);r.pop('generation_settings',None);r.pop('scores',None)
            rows.append(r)
    return sorted(rows,key=lambda r:r['available_at'],reverse=True)

def save_feedback(d,known):
    required={'target_id','reviewer','decision','correction','usefulness','supported','notes'}
    if set(d)!=required or d['decision'] not in ('confirm','reject','correct') or any(not isinstance(d[k],str) or len(d[k])>2000 for k in ('target_id','reviewer','decision','correction','notes')):raise ValueError()
    if not d['reviewer'].strip() or (d['decision']=='correct' and not d['correction'].strip()):raise ValueError()
    if any(type(d[k]) is not int or not 1<=d[k]<=5 for k in ('usefulness','supported')):raise ValueError()
    if d['target_id'] not in known:raise ValueError()
    ident=str(uuid.uuid4());at=datetime.now(timezone.utc).isoformat()
    with connect() as c:c.execute('INSERT INTO feedback VALUES(?,?,?,?,?,?,?,?,?)',(ident,at,d['target_id'],d['reviewer'],d['decision'],d['correction'],d['usefulness'],d['supported'],d['notes']))
    return {'id':ident,'learning_applied':False}
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def reply(self,code,value,mime='application/json'):
        b=json.dumps(value,default=str).encode() if mime=='application/json' else value
        self.send_response(code);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(b)
    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:8766','localhost:8766'):self.reply(403,{});return
        if self.path=='/api/results':self.reply(200,{'results':results(),'feedback_learning':False});return
        if self.path=='/api/reviews':
            with connect() as c:r=[dict(x) for x in c.execute('SELECT * FROM feedback ORDER BY at DESC LIMIT 100')]
            self.reply(200,r);return
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','application/javascript'),'/style.css':('style.css','text/css')}
        if self.path not in files:self.reply(404,{});return
        name,mime=files[self.path];self.reply(200,(WEB/name).read_bytes(),mime)
    def do_POST(self):
        if self.headers.get('Host') not in ('127.0.0.1:8766','localhost:8766') or self.headers.get('Origin') not in ('http://127.0.0.1:8766','http://localhost:8766') or self.headers.get('X-Copilot-Action')!='review':self.reply(403,{});return
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=8192 or self.headers.get('Content-Type')!='application/json':raise ValueError()
            d=json.loads(self.rfile.read(n));at=datetime.now(timezone.utc).isoformat()
            if self.path=='/api/display-ack':
                known={r['result_id'] for r in results()}
                if set(d)!={'result_ids'} or not isinstance(d['result_ids'],list) or len(d['result_ids'])>300 or any(i not in known for i in d['result_ids']):raise ValueError()
                with connect() as c:c.executemany('INSERT OR IGNORE INTO display_ack VALUES(?,?)',[(i,at) for i in d['result_ids']])
                self.reply(200,{'recorded':len(d['result_ids'])});return
            if self.path=='/api/feedback':
                self.reply(201,save_feedback(d,{r['result_id'] for r in results()}));return
            self.reply(404,{'error':'Read-only application; no network control endpoint'})
        except (ValueError,TypeError,KeyError):self.reply(400,{'error':'Invalid feedback or acknowledgement'})
if __name__=='__main__':
    with connect():pass
    print('Study viewer http://127.0.0.1:8766',flush=True);ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
