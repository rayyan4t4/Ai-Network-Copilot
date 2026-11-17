import json,unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import Mock
from evaluation.protocol import packet,mask
from live.provider import diagnose_live
ROOT=Path(__file__).resolve().parents[2]
class LiveAdapterTests(unittest.TestCase):
    def setUp(self):
        self.bundle=json.loads((ROOT/'research/pilot/f8ba1161-063f-397e-2549-14f2dbf2e264/original.json').read_text())
        self.incident=dict(packet(self.bundle)['primary'],incident_id='11111111-1111-1111-1111-111111111111')
        self.clock=lambda:datetime.fromisoformat(self.bundle['as_of'])+timedelta(seconds=5)
    def test_uses_same_packet_and_preserves_response_without_forcing_target(self):
        response={'status':'ok','request':{'facts':[]},'response':{'disposition':'inconclusive','fault_class':'inconclusive','device_id':'','interface':'','summary':'Insufficient interpretation'},'validation':{'valid':True},'read_only_checks':[]}
        call=Mock(return_value=response);r=diagnose_live(self.incident,self.bundle,call,self.clock)
        self.assertEqual(call.call_args.args[0],packet(self.bundle));self.assertEqual(r['status'],'validated_structure')
        self.assertEqual(r['response']['fault_class'],'inconclusive');self.assertEqual(r['incident_id'],self.incident['incident_id']);self.assertTrue(r['model_called'])
    def test_gate_withholds_without_provider_call(self):
        call=Mock();r=diagnose_live(self.incident,mask(self.bundle,'interface_shutdown'),call,self.clock)
        call.assert_not_called();self.assertEqual(r['status'],'inconclusive');self.assertFalse(r['model_called'])
    def test_stale_bundle_cannot_call_model(self):
        call=Mock();r=diagnose_live(self.incident,self.bundle,call,lambda:self.clock()+timedelta(minutes=2))
        call.assert_not_called();self.assertEqual(r['status'],'cancelled_stale')
    def test_different_incident_cannot_reuse_window(self):
        call=Mock();self.incident['fingerprint']='different';r=diagnose_live(self.incident,self.bundle,call,self.clock)
        call.assert_not_called();self.assertEqual(r['status'],'cancelled_stale')
if __name__=='__main__':unittest.main()
