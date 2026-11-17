"""Descriptive failure and acquisition audit; does not alter frozen scores."""
import collections,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from run_study import save,now
from evaluation.protocol import score
control=ROOT/'.local/evaluation/control';base=ROOT/'research';schedule=json.loads((control/'final-schedule.json').read_text())
summary={};lags=[];gates=collections.Counter();intervals=[];snapshot_intervals=[]
for truth in schedule:
    c=json.loads((control/'final'/(truth['case_id']+'.json')).read_text());lags.append(c['capture_lag_seconds']);case=base/'final'/truth['case_id'];p=json.loads((case/'analysis.json').read_text())
    gates[truth['category']+':'+(p['primary']['gate']['status'] if p['primary'] else 'no_candidate')]+=1
    raw=json.loads((case/'observations.json').read_text())
    intervals.extend(s['interval_s'] for s in raw['samples'] if s.get('rate_status')=='valid' and s.get('interval_s'))
    from datetime import datetime
    snaps=collections.defaultdict(list)
    for s in raw['snapshots']:snaps[s['device_id']].append(datetime.fromisoformat(s['observed_at']))
    for values in snaps.values():
        if len(values)>=2:values.sort();snapshot_intervals.append((values[-1]-values[-2]).total_seconds())
for approach in ('B1','B2','no_gate','full'):
    failures=collections.Counter();by_condition=collections.Counter();validations=collections.Counter();http=collections.Counter();calls=0;attempts=0
    for truth in schedule:
        r=json.loads((base/'final'/truth['case_id']/(approach+'.json')).read_text());p=r.get('prediction',{});s=score(truth,r)
        calls+=bool(r.get('model_called'));attempts+=len(r.get('attempt_history',[]))
        for a in r.get('attempt_history',[]):
            if a.get('http_status'):http[str(a['http_status'])]+=1
        for err in r.get('validation',{}).get('errors',[]):validations[err]+=1
        if r['status']!='ok':by_condition[truth['category']+':'+r['status']]+=1
        if not s['fault_instance'] or s['exact_root_correct']:continue
        if r['status']!='ok':reason=r['status']
        elif p.get('disposition')=='inconclusive':reason='valid_abstention_on_diagnosable_fault'
        elif p.get('fault_class')!=truth['underlying_class']:reason='wrong_class'
        elif p.get('device_id')!=truth['device_id']:reason='wrong_device'
        else:reason='wrong_interface'
        failures[reason]+=1
    summary[approach]={'root_miss_reasons':dict(failures),'errors_by_condition':dict(by_condition),'validation_errors':dict(validations),'provider_http_attempt_errors':dict(http),'model_evaluations_requested':calls,'provider_attempts_including_retries':attempts}
save(base/'descriptive-audit.json',{'recorded_at':now(),'scope':'Post-study descriptive breakdown. Primary metrics and frozen scoring unchanged. No semantic or human ratings inferred.','approaches':summary,'capture_lag_seconds':{'median':statistics.median(lags),'maximum':max(lags)},'observed_valid_counter_interval_seconds_median':statistics.median(intervals) if intervals else None,'observed_snapshot_separation_seconds_median':statistics.median(snapshot_intervals) if snapshot_intervals else None,'primary_gate_by_condition':dict(gates)})
print('Saved descriptive failure and acquisition audit.')
