"""Fixed denominators, error accounting, paired tables and reviewer materials."""
import argparse,csv,hashlib,json,math,random,sqlite3,statistics,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from evaluation.protocol import CLASSES,score
from run_study import save
BASE=ROOT/'research';CONTROL=ROOT/'.local/evaluation/control'
APPROACHES=['B1','B2','no_gate','full']
def percentile(v,p):
    if not v:return None
    v=sorted(v);x=(len(v)-1)*p;a=int(x);return v[a]+(v[min(a+1,len(v)-1)]-v[a])*(x-a)
def wilson(k,n):
    if not n:return None
    z=1.96;d=1+z*z/n;m=(k/n+z*z/(2*n))/d;h=z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/d;return [m-h,m+h]
def analyze(phase='final'):
    schedule=json.loads((CONTROL/(phase+'-schedule.json')).read_text());records=[];metrics={};confusion={};per_fault={}
    ack={};db=ROOT/'.local/evaluation/reviews.sqlite3'
    if db.exists():
        with sqlite3.connect(db) as c:ack=dict(c.execute('SELECT result_id,at FROM display_ack'))
    for a in APPROACHES:
        totals=Counter();lat=[];api=[];display=[];matrix=defaultdict(Counter);faults=defaultdict(Counter)
        for truth in schedule:
            p=BASE/phase/truth['case_id']/(a+'.json')
            if not p.exists():totals['missing']+=1;continue
            r=json.loads(p.read_text());s=score(truth,r);totals['recorded']+=1
            for k,v in s.items():
                if v is True:totals[k]+=1
            pred=r.get('prediction',{});label=pred.get('fault_class','error') if r['status']=='ok' else 'error'
            matrix[truth['category']][label]+=1
            if s['fault_instance']:
                faults[truth['category']]['n']+=1;faults[truth['category']]['correct']+=bool(s['exact_root_correct'])
            if r['status']=='ok':lat.append(r['pipeline_latency_ms'])
            if r.get('api_latency_ms') is not None:api.append(r['api_latency_ms'])
            if r['result_id'] in ack:
                from datetime import datetime
                display.append((datetime.fromisoformat(ack[r['result_id']])-datetime.fromisoformat(r['started_at'])).total_seconds()*1000)
            records.append({'case_id':truth['case_id'],'sequence':truth['sequence'],'category':truth['category'],'underlying_class':truth['underlying_class'],'true_device':truth['device_id'],'true_interface':truth['interface'],'approach':a,'status':r['status'],'predicted_class':label,'predicted_device':pred.get('device_id',''),'predicted_interface':pred.get('interface',''),'disposition':pred.get('disposition',''),'exact_root_correct':s['exact_root_correct'],'correct_abstention':s['correct_abstention'],'pipeline_latency_ms':r['pipeline_latency_ms'],'api_latency_ms':r.get('api_latency_ms'),'display_acknowledged':r['result_id'] in ack})
        tp,fp,fn=totals['detection_tp'],totals['detection_fp'],totals['detection_fn'];precision=tp/(tp+fp) if tp+fp else 0;recall=tp/(tp+fn) if tp+fn else 0
        metrics[a]={'counts':dict(totals),'detection_precision':precision,'detection_recall':recall,'detection_f1':2*precision*recall/(precision+recall) if precision+recall else 0,
          'root_accuracy_faults':totals['exact_root_correct']/50,'root_wilson_95':wilson(totals['exact_root_correct'],50),
          'insufficient_correct_abstention':totals['correct_abstention']/10,
          'pipeline_success_median_ms':statistics.median(lat) if lat else None,'pipeline_success_p95_ms':percentile(lat,.95),
          'api_attempt_median_ms':statistics.median(api) if api else None,
          'browser_display_ack_count':len(display),'browser_display_median_ms':statistics.median(display) if display else None,
          'denominators':{'diagnosable_faults':50,'healthy':10,'insufficient':10},
          'latency_scope':'Recorded-window replay processing to result-file availability, including local request spacing when applicable. API duration separate. Incident injection to browser display is not established by these measurements.'}
        confusion[a]={k:dict(v) for k,v in matrix.items()};per_fault[a]={k:dict(v) for k,v in faults.items()}
    result={'phase':phase,'planned_instances':len(schedule),'recorded_outputs':len(records),'metrics':metrics,'confusion':confusion,'per_fault':per_fault,'human_review_status':'pending two independent human reviewers','browser_ui_status':'Browser origin access rejected; display latency and visual UI checks unverified.'}
    save(BASE/'results.json',result)
    if records:
        with (BASE/'results.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    return result
def review_pack():
    out=ROOT/'docs/review';out.mkdir(parents=True,exist_ok=True)
    mapping={};rows=[];rng=random.Random(20261118)
    schedule=json.loads((CONTROL/'final-schedule.json').read_text())
    import html
    pages=['<!doctype html><meta charset="utf-8"><title>Independent diagnosis review</title><style>body{font:16px Arial;max-width:1000px;margin:40px auto;line-height:1.5}pre{white-space:pre-wrap;background:#f3f5f6;padding:18px}article{page-break-after:always;border-top:1px solid #bbb;padding-top:20px}</style><h1>Independent diagnosis review</h1><p>Use the separate reviewer CSV. Approach identities are withheld. Rate each output independently before discussing with the other reviewer. No completed ratings are supplied.</p>']
    for truth in schedule:
        approaches=rng.sample(APPROACHES,4)
        for a in approaches:
            p=BASE/'final'/truth['case_id']/(a+'.json')
            if not p.exists():continue
            r=json.loads(p.read_text());ident=str(uuid_from_hash(r['result_id']));mapping[ident]={'result_id':r['result_id'],'approach':a,'case_id':truth['case_id']}
            packet=json.loads((p.parent/'analysis.json').read_text())
            view={'review_id':ident,'observations':packet['facts'],'candidate_hypotheses':packet['candidates'],'status':r['status'],'interpretation':r.get('response',r.get('prediction')),'read_only_checks':r.get('read_only_checks',[])}
            (out/(ident+'.json')).write_text(json.dumps(view,indent=2))
            pages.append('<article><h2>'+ident+'</h2><pre>'+html.escape(json.dumps(view,indent=2))+'</pre></article>')
            rows.append({'review_id':ident,'reviewer_name':'','claim_count':'','unsupported_claim_count':'','recommendation_count':'','relevant_recommendation_count':'','read_only_recommendation_count':'','supported_recommendation_count':'','usefulness_1_to_5':'','evidence_support_1_to_5':'','decision_confirm_reject_correct':'','correction':'','notes':''})
    (out/'Review pack.html').write_text('\n'.join(pages),encoding='utf-8');save(CONTROL/'review-blinding-map.json',mapping)
    for reviewer in (1,2):
        with (out/f'Reviewer {reviewer}.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/'Review instructions.md').write_text('''# Independent review instructions

Two real team members complete separate CSV files without consulting each other. Approach identities are withheld, although input differences may reveal some conditions. Open Review pack.html and use its review IDs. Do not enter ratings for provider errors; explain not assessable in notes.

Count each independently verifiable factual claim. An unsupported claim is absent from, contradicted by, or stronger than the observations. Mark uncertain alternatives as hypotheses, not facts. Count each distinct suggested check, then mark relevance to the incident, whether it is read only, and support from the observations. Do not treat valid citation IDs as proof of prose support. Usefulness and support use 1 very poor through 5 very good. Confirm, reject or correct the interpretation and explain corrections.

Keep initial ratings unchanged for agreement analysis. Discuss disagreements only after both sheets are complete and save a separate adjudication sheet. The project does not apply learning from feedback. No human-review metric is available until both people return their completed forms.
''')
def uuid_from_hash(value):
    import uuid
    return uuid.UUID(hashlib.sha256(value.encode()).hexdigest()[:32])
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--pilot',action='store_true');ap.add_argument('--review',action='store_true');a=ap.parse_args();r=analyze('pilot' if a.pilot else 'final');print(json.dumps(r['metrics'],indent=2))
    if a.review:review_pack()
