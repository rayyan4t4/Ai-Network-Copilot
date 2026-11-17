"""Label-free adapters and prespecified scoring for the paired study."""
import copy,re
from evaluation.engine import analyze, evaluate_gate,command,neighbors,dt

CLASSES=['interface_shutdown','ospf_loss','acl_fault','high_utilization','unreachability']
PRIORITY={k:i for i,k in enumerate(CLASSES)}

def packet(bundle):
    result=analyze(bundle)
    candidates=sorted(result['incidents'],key=lambda c:(PRIORITY[c['fault_class']],-len(c['affected_devices']),c['device_id']))
    primary=candidates[0] if candidates else None
    facts=[{k:f[k] for k in ('evidence_id','device_id','kind','observed_at','source','is_stale','summary')} for f in result['facts'] if not f['is_stale']]
    # Only normalized controlled summaries leave this machine. Values and raw
    # snapshots, configurations, addresses and intervention labels stay local.
    selected=set(i for c in candidates[:6] for i in [f['evidence_id'] for f in c['facts']])
    if selected:facts=[f for f in facts if f['evidence_id'] in selected]
    else:facts=[f for f in facts if f['kind'] in ('probe','poll')][:60]
    return {'as_of':bundle['as_of'],'facts':facts,'devices':[d['device_id'] for d in result['health']],
      'candidates':[{k:c[k] for k in ('fault_class','device_id','interface','affected_devices','topology_path')} for c in candidates[:6]],
      'primary':primary,'health_counts':{s:sum(d['state']==s for d in result['health']) for s in ('healthy','unknown','unreachable')}}

def mask(bundle,kind):
    """Withhold a source family from a copy, never create observations."""
    b=copy.deepcopy(bundle)
    if kind in ('interface_shutdown','ospf_loss'):b['events']=[]
    elif kind=='acl_fault':
        # Keep latest snapshot, withhold earlier counters needed for a delta.
        seen=set();items=[]
        for s in sorted(b['snapshots'],key=lambda s:s['observed_at'],reverse=True):
            if s['device_id'] not in seen:items.append(s);seen.add(s['device_id'])
        b['snapshots']=items
    elif kind=='high_utilization':
        for i in b['interfaces']:i['capacity_source']='unavailable'
    elif kind=='unreachability':b['snapshots']=[];b['samples']=[]
    return b

def b1(bundle):
    """Uncorrelated direct alert baseline: no topology, matrix or model."""
    samples=sorted(bundle['samples'],key=lambda x:x['observed_at'],reverse=True);seen=set()
    for s in samples:
        ident=s['interface_id']
        if ident in seen:continue
        seen.add(ident)
        if s['admin_status']==2 and ident.split(':')[-1].startswith('eth'):
            return prediction('interface_shutdown',s['device_id'],ident.split(':')[-1])
    latest_snap={}
    for snap in sorted(bundle['snapshots'],key=lambda s:s['observed_at'],reverse=True):latest_snap.setdefault(snap['device_id'],snap)
    for event in sorted(bundle['events'],key=lambda e:e['received_at'],reverse=True):
        if event['program']!='ospfd' or event['identity_status']!='source_and_hostname' or (dt(bundle['as_of'])-dt(event['received_at'])).total_seconds()>90:continue
        match=re.search(r' on (eth\d+).*Full\s*->\s*(Deleted|Down|Init)',event['message'])
        if not match:continue
        snap=latest_snap.get(event['device_id']);ns=command(snap,'ospf_neighbors') if snap else None
        if ns and any(n.get('ifaceName','').split(':')[0]==match[1] and 'Full' in n.get('state','') for n in neighbors(ns)):continue
        return prediction('ospf_loss',event['device_id'],match[1])
    for s in samples:
        if s.get('rate_status')=='valid' and max(s.get('in_utilization_pct') or 0,s.get('out_utilization_pct') or 0)>=80:
            return prediction('high_utilization',s['device_id'],s['interface_id'].split(':')[-1])
    latest={}
    for p in sorted(bundle['probes'],key=lambda p:p['observed_at'],reverse=True):latest.setdefault(p['device_id'],p)
    for d,p in sorted(latest.items()):
        if p['status']=='timeout':return prediction('unreachability',d,'')
    return prediction('healthy','','',False)

def prediction(kind,device='',interface='',detected=True):
    return {'fault_class':kind,'device_id':device,'interface':interface or '',
      'disposition':'inconclusive' if kind=='inconclusive' else 'supported','incident_detected':detected}

def score(truth,output):
    kind=truth['category'];underlying=truth['underlying_class'];valid=output.get('status')=='ok'
    p=output.get('prediction',{});fault=kind not in ('healthy','insufficient')
    detected=bool(p.get('incident_detected')) if valid else False
    root=valid and p.get('disposition')=='supported' and p.get('fault_class')==underlying and p.get('device_id')==truth['device_id'] and (not truth.get('interface') or p.get('interface')==truth['interface'])
    return {'fault_instance':fault,'healthy_instance':kind=='healthy','insufficient_instance':kind=='insufficient',
      'detection_tp':fault and detected,'detection_fn':fault and not detected,
      'detection_fp':kind=='healthy' and (detected or not valid),'detection_tn':kind=='healthy' and valid and not detected,
      'exact_root_correct':bool(root) if fault else None,
      'correct_abstention':bool(valid and p.get('disposition')=='inconclusive') if kind=='insufficient' else None,
      'error':not valid}
