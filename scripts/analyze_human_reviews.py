"""Validate real reviewer CSVs before computing any human-quality results."""
import csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from evaluation.human_metrics import aggregate,kappa
from run_study import save,now
mapping_path=ROOT/'.local/evaluation/control/review-blinding-map.json'
if not mapping_path.exists():
    print('Pending: final blinded review pack has not been generated.');raise SystemExit(0)
mapping=json.loads(mapping_path.read_text());review=ROOT/'docs/review';raters=[];issues=[];provenance=[];completed=[]
count_fields=['claim_count','unsupported_claim_count','recommendation_count','relevant_recommendation_count','read_only_recommendation_count','supported_recommendation_count']
scale_fields=['usefulness_1_to_5','evidence_support_1_to_5']
for number in (1,2):
    ratings={};names=set();path=review/f'Reviewer {number}.csv';seen=set();applicable=0
    for row in csv.DictReader(path.open(newline='',encoding='utf-8-sig')):
        ident=row.get('review_id','')
        if ident not in mapping or ident in seen:issues.append({'reviewer':number,'reason':'Unknown or duplicate review ID','review_id':ident});continue
        seen.add(ident);item=mapping[ident]
        record=json.loads((ROOT/'research/final'/item['case_id']/(item['approach']+'.json')).read_text())
        if record['status']!='ok':continue
        applicable+=1
        if not any(row.get(k,'').strip() for k in count_fields+scale_fields+['reviewer_name','decision_confirm_reject_correct']):continue
        try:
            if not row.get('reviewer_name','').strip():raise ValueError('Reviewer name required')
            parsed={k:int(row[k]) for k in count_fields+scale_fields}
            if any(parsed[k]<0 for k in count_fields):raise ValueError('Negative count')
            if parsed['unsupported_claim_count']>parsed['claim_count']:raise ValueError('Unsupported claims exceed claims')
            if any(parsed[k]>parsed['recommendation_count'] for k in count_fields[3:]):raise ValueError('Recommendation subcount exceeds total')
            if any(not 1<=parsed[k]<=5 for k in scale_fields):raise ValueError('Rating outside 1 to 5')
            decision=row.get('decision_confirm_reject_correct','').strip().lower()
            if decision not in ('confirm','reject','correct'):raise ValueError('Invalid decision')
            if decision=='correct' and not row.get('correction','').strip():raise ValueError('Correction text required')
            parsed['decision']=decision;parsed['approach']=item['approach'];ratings[ident]=parsed;names.add(row['reviewer_name'].strip())
        except (ValueError,TypeError,KeyError) as e:issues.append({'reviewer':number,'review_id':ident,'reason':str(e)})
    if seen!=set(mapping):issues.append({'reviewer':number,'reason':'Missing rows','missing_count':len(set(mapping)-seen)})
    if len(names)>1:issues.append({'reviewer':number,'reason':'Each independent sheet must identify one reviewer consistently'})
    provenance.append(sorted(names));raters.append(ratings);completed.append({'reviewer':number,'applicable_outputs':applicable,'completed':len(ratings)})
if provenance[0] and provenance[1] and provenance[0]==provenance[1]:issues.append({'reason':'Two distinct reviewers required'})
complete=not issues and all(r['completed']==r['applicable_outputs'] and r['completed']>0 for r in completed)
result={'recorded_at':now(),'status':'supplied_sheets_complete' if complete else 'pending_human_reviews','counts':completed,'validation_issues':issues,'metrics':None,
  'provenance_boundary':'Calculations use supplied CSV judgments. Software cannot verify human identity or reviewer independence. Team confirmation is required before research claims. No ratings are generated, imputed or learned.'}
if complete:
    result['metrics']={'by_reviewer':{},'agreement':{}}
    for index,ratings in enumerate(raters,1):result['metrics']['by_reviewer'][str(index)]={a:aggregate([r for r in ratings.values() if r['approach']==a]) for a in ('B1','B2','no_gate','full')}
    ids=sorted(set(raters[0])&set(raters[1]))
    for field in scale_fields+['decision']:
        result['metrics']['agreement'][field]=kappa([raters[0][i][field] for i in ids],[raters[1][i][field] for i in ids],[1,2,3,4,5] if field!='decision' else None)
save(ROOT/'research/human-review-status.json',result)
print(result['status'],completed,'metrics computed',complete)
