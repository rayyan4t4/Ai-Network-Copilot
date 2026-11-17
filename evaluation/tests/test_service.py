import json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from evaluation import service
class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.patch=patch.object(service,'DB',Path(self.temp.name)/'test.sqlite3');self.patch.start()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),service.Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_address[1]);self.target=service.results()[0]['result_id']
    def tearDown(self):self.server.shutdown();self.server.server_close();self.patch.stop();self.temp.cleanup()
    def post(self,path,data,origin=True):
        headers={'Host':'127.0.0.1:8766','Content-Type':'application/json','X-Copilot-Action':'review'}
        if origin:headers['Origin']='http://127.0.0.1:8766'
        req=urllib.request.Request(self.url+path,data=json.dumps(data).encode(),headers=headers)
        try:
            with urllib.request.urlopen(req) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def feedback(self):return {'target_id':self.target,'reviewer':'AUTOMATED TEST ONLY','decision':'confirm','correction':'','usefulness':3,'supported':3,'notes':'Isolated test database, not research feedback.'}
    def test_confirm_persisted_without_learning(self):
        code,r=self.post('/api/feedback',self.feedback());self.assertEqual(code,201);self.assertFalse(r['learning_applied'])
        with service.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM feedback').fetchone()[0],1)
    def test_correct_requires_correction(self):
        data=self.feedback();data['decision']='correct';self.assertEqual(self.post('/api/feedback',data)[0],400)
        data['correction']='Observed root differs';self.assertEqual(self.post('/api/feedback',data)[0],201)
    def test_reject_saved(self):
        data=self.feedback();data['decision']='reject';self.assertEqual(self.post('/api/feedback',data)[0],201)
    def test_missing_origin_denied(self):self.assertEqual(self.post('/api/feedback',self.feedback(),False)[0],403)
    def test_unknown_target_denied(self):
        data=self.feedback();data['target_id']='unknown';self.assertEqual(self.post('/api/feedback',data)[0],400)
    def test_command_endpoint_absent(self):self.assertEqual(self.post('/api/execute',{'command':'x'})[0],404)
    def test_invalid_rating_denied(self):
        data=self.feedback();data['usefulness']=9;self.assertEqual(self.post('/api/feedback',data)[0],400)
if __name__=='__main__':unittest.main()
