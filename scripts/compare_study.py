"""Independent calls for four approaches on each immutable observation case."""
import argparse,hashlib,json,random,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from evaluation.protocol import b1,packet,prediction,score
from evaluation.model import call
from run_study import save,now
BASE=ROOT/'research';CONTROL=ROOT/'.local/evaluation/control'
PROFILE=json.loads((ROOT/'evaluation/profile.json').read_text())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pilot',action='store_true');ap.add_argument('--follow',action='store_true');a=ap.parse_args();phase='pilot' if a.pilot else 'final'
    schedule=json.loads((CONTROL/(phase+'-schedule.json')).read_text());attempts=CONTROL/'model-attempts.json';last=0
    if not a.pilot:
        from evaluation.freeze import verify
        verify()
    while True:
        pending=False
        for truth in schedule:
            if not a.pilot:verify()
            case=BASE/phase/truth['case_id'];obs=case/'observations.json';ctl=CONTROL/phase/(truth['case_id']+'.json')
            if not obs.exists() or not ctl.exists() or not json.loads(ctl.read_text()).get('complete'):pending=True;continue
            for approach in random.Random(truth['case_id']).sample(['B1','B2','no_gate','full'],4):
                target=case/(approach+'.json')
                if target.exists():continue
                start=time.monotonic();began=now();bundle=json.loads(obs.read_text());p=packet(bundle)
                record={'result_id':str(uuid.uuid4()),'case_id':truth['case_id'],'phase':phase,'approach':approach,'started_at':began,'observation_sha256':hashlib.sha256(obs.read_bytes()).hexdigest()}
                if approach=='B1':record.update(status='ok',prediction=b1(bundle))
                elif approach=='full' and p['primary'] and p['primary']['gate']['status']!='sufficient':
                    record.update(status='ok',prediction=prediction('inconclusive',detected=True),model_called=False,gate=p['primary']['gate'])
                else:
                    wait=max(0,PROFILE['model_minimum_spacing_seconds']-(time.monotonic()-last))
                    if wait:time.sleep(wait)
                    history=[]
                    for attempt in range(2):
                        calls=json.loads(attempts.read_text()) if attempts.exists() else []
                        if len(calls)>=PROFILE['maximum_study_generation_attempts']:raise RuntimeError('Study request budget reached')
                        calls.append({'at':now(),'phase':phase,'case_id':truth['case_id'],'approach':approach,'attempt':attempt+1});save(attempts,calls)
                        response=call(p,approach,PROFILE);history.append(response);last=time.monotonic()
                        if attempt==0 and response.get('http_status') in (429,503):time.sleep(60 if response['http_status']==429 else 30);continue
                        break
                    record.update(history[-1]);record['attempt_history']=history;record['model_called']=True
                record['pipeline_latency_ms']=round((time.monotonic()-start)*1000);record['available_at']=now();record['scores']=score(truth,record);save(target,record)
                print(phase,truth['sequence'],approach,record['status'],record.get('prediction'),flush=True)
                # Preserve service errors. Do not hammer a provider quota limit.
                if record.get('http_status')==429:time.sleep(60)
        if not pending or not a.follow:break
        time.sleep(5)
if __name__=='__main__':main()
