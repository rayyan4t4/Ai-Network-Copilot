"""Use the same unrestricted classifier for live and recorded evidence."""
import hashlib,json,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from evaluation.protocol import packet
from evaluation.model import call,SYSTEM
from copilot.provider import render_checks,allowed_commands,retrieve
ROOT=Path(__file__).resolve().parents[1]
def diagnose_live(incident,bundle,model_call=call,clock=lambda:datetime.now(timezone.utc)):
    start=time.monotonic();profile=json.loads((ROOT/'evaluation/profile.json').read_text())
    record={'diagnosis_id':str(uuid.uuid4()),'incident_id':incident['incident_id'],'recorded_at':clock().isoformat(),
      'model':profile['model'],'prompt_version':'study-final-1-live','system_instruction':SYSTEM,'status':'pending','model_called':False}
    current=packet(bundle);primary=current['primary'];age=(clock()-datetime.fromisoformat(bundle['as_of'])).total_seconds()
    if age< -5 or age>45 or not primary or primary['fingerprint']!=incident['fingerprint']:
        record.update(status='cancelled_stale',response={'reason':'A fresh matching incident window is no longer available. No model call made.'},validation={'valid':False,'model_called':False})
    else:
        record['evidence_package']=dict(primary,incident_id=incident['incident_id'])
        record['structured_evidence']=current
        if primary['gate']['status']!='sufficient':
            record.update(status='inconclusive',response={'reason':'Evidence gate withheld the request.','missing':primary['gate']['missing']},validation={'valid':True,'model_called':False})
            record['read_only_checks']=render_checks(primary,allowed_commands(primary,retrieve(primary)))
        else:
            try:
                result=model_call(current,'full',profile);record.update(result);record['model_called']=True
                record['status']='validated_structure' if result['status']=='ok' else result['status']
                record['prompt_hash']=hashlib.sha256((SYSTEM+json.dumps(result['request'],sort_keys=True)).encode()).hexdigest()
            except (RuntimeError,ValueError,FileNotFoundError):
                record.update(status='rejected',response={'reason':'Provider configuration or approved input-scope check failed. No accepted interpretation.'},validation={'valid':False,'semantic_review_required':True})
    record['latency_ms']=round((time.monotonic()-start)*1000)
    return record
