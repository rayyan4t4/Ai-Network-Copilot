"""Integrity and attempt audit, supplementary to unchanged frozen scoring."""
import collections,hashlib,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from evaluation.freeze import verify
from run_study import save,now
base=ROOT/'research';control=ROOT/'.local/evaluation/control';manifest=verify()
schedule=json.loads((control/'final-schedule.json').read_text());checks=[];attempts=[];status=collections.Counter();models=collections.Counter();mask_summary=[]
def check(name,passed,detail=None):checks.append({'check':name,'passed':bool(passed),'detail':detail})
check('Frozen source hashes unchanged',True)
check('70 scheduled cases and ten per category',len(schedule)==70 and set(collections.Counter(r['category'] for r in schedule).values())=={10})
for truth in schedule:
    case=base/'final'/truth['case_id'];ctl=control/'final'/(truth['case_id']+'.json')
    if not ctl.exists():check('Acquired '+truth['case_id'],False);continue
    c=json.loads(ctl.read_text());check('Restored '+truth['case_id'],c.get('complete') and c.get('restoration_verified') and c.get('intervention',{}).get('exit_code')==0)
    obs=case/'observations.json'
    for approach in ('B1','B2','no_gate','full'):
        p=case/(approach+'.json')
        if not p.exists():check('Output '+truth['case_id']+' '+approach,False);continue
        r=json.loads(p.read_text());status[approach+':'+r['status']]+=1
        check('Paired input '+truth['case_id']+' '+approach,r['observation_sha256']==hashlib.sha256(obs.read_bytes()).hexdigest())
        for a in r.get('attempt_history',[]):
            attempts.append({'case_id':truth['case_id'],'approach':approach,'status':a['status'],'http_status':a.get('http_status'),'api_latency_ms':a['api_latency_ms']})
            if a.get('model_version'):models[a['model_version']]+=1
            serialized=json.dumps(a['request']);import re
            check('Approved normalized request '+truth['case_id']+' '+approach,not re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b',serialized) and not any(k in a['request'] for k in ('ground_truth','intervention','raw','configuration','category','case_id')))
        if truth['category']=='insufficient' and approach=='full':mask_summary.append({'case_id':truth['case_id'],'underlying_class':truth['underlying_class'],'model_called':r.get('model_called',False),'prediction':r.get('prediction'),'status':r['status']})
    a=case/'full.json';b=case/'no_gate.json'
    if a.exists() and b.exists():
        ra,rb=json.loads(a.read_text()),json.loads(b.read_text())
        if ra.get('model_called') and rb.get('model_called'):check('Identical structured input '+truth['case_id'],ra['request']==rb['request'])
ledger=json.loads((control/'model-attempts.json').read_text());profile=json.loads((ROOT/'evaluation/profile.json').read_text());check('Declared request cap respected',len(ledger)<=profile['maximum_study_generation_attempts'],{'attempts':len(ledger),'declared_cap':profile['maximum_study_generation_attempts'],'resource_amendment':(base/'resource-amendment.json').exists()})
result={'recorded_at':now(),'passed':all(c['passed'] for c in checks),'checks':checks,'status_counts':dict(status),'model_versions':dict(models),'final_attempt_count':len(attempts),'all_study_attempt_count':len(ledger),'attempt_http_status_counts':dict(collections.Counter(str(a['http_status']) for a in attempts)),'all_final_attempt_latency_median_ms':statistics.median(a['api_latency_ms'] for a in attempts) if attempts else None,'insufficient_full_outcomes':mask_summary,'human_review':'pending','browser_render_acknowledgements':'none synthesized; access rejected'}
save(base/'integrity-audit.json',result);save(base/'attempt-audit.json',attempts)
print('Integrity audit',result['passed'],'checks',len(checks),'outputs',sum(status.values()),'attempts',len(attempts))
if not result['passed']:sys.exit(1)
