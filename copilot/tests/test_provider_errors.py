import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]));sys.path.insert(0,str(Path(__file__).parent))
from fixtures import outage,uid
from copilot.engine import analyze
from copilot.provider import diagnose

class ProviderErrorTests(unittest.TestCase):
    def setUp(self):
        self.package=next(c for c in analyze(outage())['incidents'] if c['fault_class']=='interface_shutdown');self.package['incident_id']=uid('mock-error')
        self.base=Path(__file__).resolve().parents[2]/'.local/runtime/test-tmp';self.base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=self.base)
        assert Path(self.tmp.name).resolve().is_relative_to(self.base.resolve())
        self.key=Path(self.tmp.name)/'key';self.key.write_text('public-unit-test-placeholder')
    def tearDown(self):
        assert Path(self.tmp.name).resolve().is_relative_to(self.base.resolve())
        self.tmp.cleanup()
    def run_mock(self,value=None,error=None):
        kwargs={'side_effect':error} if error else {'return_value':io.BytesIO(json.dumps(value).encode())}
        with patch('copilot.provider.transmission_approved',return_value=True),patch('urllib.request.urlopen',**kwargs):return diagnose(self.package,self.key)
    def test_http_quota_error_visible_and_not_retried(self):
        error=urllib.error.HTTPError('https://example.invalid',429,'quota',{},io.BytesIO(b'{"error":{"status":"RESOURCE_EXHAUSTED","message":"quota"}}'))
        r=self.run_mock(error=error);self.assertEqual(r['status'],'provider_error');self.assertEqual(r['response']['http_status'],429)
    def test_network_timeout_visible(self):
        r=self.run_mock(error=TimeoutError());self.assertEqual(r['status'],'provider_error');self.assertIn('timeout',r['response']['reason'])
    def test_malformed_json_model_text_rejected(self):
        r=self.run_mock({'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'not JSON'}]}}]});self.assertEqual(r['status'],'rejected')
    def test_blocked_response_rejected(self):
        self.assertEqual(self.run_mock({'candidates':[]})['status'],'rejected')
    def test_truncated_response_rejected(self):
        self.assertEqual(self.run_mock({'candidates':[{'finishReason':'MAX_TOKENS'}]})['status'],'rejected')
    def test_external_approval_guard_never_reads_key(self):
        with patch('copilot.provider.transmission_approved',return_value=False),patch('urllib.request.urlopen',side_effect=AssertionError('No request')):
            r=diagnose(self.package,'missing');self.assertEqual(r['status'],'approval_required')
    def test_archived_evidence_not_mutated_by_later_incident_update(self):
        with patch('copilot.provider.transmission_approved',return_value=False):r=diagnose(self.package,'missing')
        count=len(r['evidence_package']['facts']);self.package['facts'].clear();self.assertEqual(len(r['evidence_package']['facts']),count)
    def test_ip_address_in_summary_is_blocked_before_transmission(self):
        self.package['facts'][0]['summary']='Unapproved address 192.168.30.10'
        with patch('copilot.provider.transmission_approved',return_value=True),patch('urllib.request.urlopen',side_effect=AssertionError('No request')):
            r=diagnose(self.package,'missing');self.assertEqual(r['status'],'rejected');self.assertFalse(r['validation']['model_called'])

if __name__=='__main__':unittest.main()
