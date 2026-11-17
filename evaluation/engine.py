"""Deterministic normalization, topology correlation and pilot sufficiency gate.

No model calls, network access, configuration changes or injection labels.
"""
import hashlib
import ipaddress
import json
import re
from collections import defaultdict,deque
from datetime import datetime,timezone
from pathlib import Path

MATRIX=json.loads(Path(__file__).with_name('matrix.json').read_text())

def ospf_mode(snapshot,interface):
    item=snapshot.get('raw',{}).get('frr_configuration',{})
    text=item.get('stdout','')
    if item.get('exit_code')!=0 or 'router ospf' not in text:return None
    lines={s.strip() for s in text.splitlines()}
    section=None
    for raw in text.splitlines():
        line=raw.strip()
        if line.startswith('interface '):section=line.split(None,1)[1]
        elif line in ('exit','!'):section=None
        elif section==interface:
            if line=='no ip ospf passive':return 'active'
            if line=='ip ospf passive':return 'passive'
    if 'no passive-interface '+interface in lines:return 'active'
    if 'passive-interface '+interface in lines or 'passive-interface default' in lines:return 'passive'
    return 'active'

def dt(value):
    if isinstance(value,datetime):return value
    return datetime.fromisoformat(value.replace('Z','+00:00'))

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()

def neighbors(raw):
    obj=json.loads(raw) if isinstance(raw,str) else raw
    return [n for group in obj.get('neighbors',{}).values() for n in group]

def command(snapshot,name):
    item=snapshot.get('raw',{}).get(name,{})
    if item.get('exit_code')!=0:return None
    try:return json.loads(item['stdout'])
    except (ValueError,KeyError,TypeError):return None

def evaluate_gate(kind,signals,contradictions=(),matrix=MATRIX):
    required=matrix['faults'][kind];weights={k:v for k,v in required.items() if k!='critical'}
    available={k:list(dict.fromkeys(signals.get(k,[]))) for k in weights}
    total=sum(weights.values());earned=sum(w for k,w in weights.items() if available[k])
    missing=[k for k in weights if not available[k]]
    critical=[k for k in required['critical'] if not available[k]]
    score=earned/total
    passed=score>=matrix['threshold'] and not critical and not contradictions
    return {'status':'sufficient' if passed else 'inconclusive','score':score,'threshold':matrix['threshold'],
      'available_weight':earned,'total_required_weight':total,'missing':missing,'missing_critical':critical,
      'contradictions':list(contradictions),'signals':available,'matrix_version':matrix['version'],
      'matrix_sha256':digest(matrix),'score_is_probability':False}

def analyze(bundle):
    at=dt(bundle['as_of']);facts=[];by_id={};devices={d['device_id']:d for d in bundle['devices']}
    ports={(l[side+'_device'],l[side+'_interface']) for l in bundle['links'] for side in ('a','b')}
    graph=defaultdict(set);edge={}
    for l in bundle['links']:
        a,b=l['a_device'],l['b_device'];graph[a].add(b);graph[b].add(a)
        edge[(a,b)]=l['a_interface'];edge[(b,a)]=l['b_interface']
    distance={'MON-HQ':0};parent={};queue=deque(['MON-HQ'])
    while queue:
        a=queue.popleft()
        for b in sorted(graph[a]):
            if b not in distance:distance[b]=distance[a]+1;parent[b]=a;queue.append(b)
    def path(target):
        p=[target]
        while p[-1] in parent:p.append(parent[p[-1]])
        return list(reversed(p))
    def add(identity,device,kind,observed,source,value,summary,ttl):
        family={'snmp':'snmp','icmp':'probe','syslog':'event','authorized_readonly_console':'snapshot'}.get(source)
        if family:ttl=MATRIX['freshness_seconds'][family]
        age=(at-dt(observed)).total_seconds()
        item={'evidence_id':identity,'device_id':device,'kind':kind,'observed_at':str(observed),
          'source':source,'age_seconds':round(age,3),'is_stale':age>ttl or age< -2,
          'value':value,'summary':summary}
        if identity not in by_id:facts.append(item);by_id[identity]=item
        return item
    def usable(item):return bool(item and not item['is_stale'])
    pollfacts={}
    for p in bundle['polls']:
        pollfacts[p['device_id']]=add('poll:'+p['poll_id'],p['device_id'],'poll',p['observed_at'],'snmp',
          {'status':p['status']},f"SNMP poll returned {p['status']}.",90)
    history=defaultdict(list);latest={}
    for s in sorted(bundle['samples'],key=lambda s:s['observed_at'],reverse=True):
        ident=s['interface_id'];history[ident].append(s)
        if ident in latest:continue
        item=add('sample:'+s['poll_id']+':'+ident,s['device_id'],'interface',s['observed_at'],'snmp',
          {k:s.get(k) for k in ('interface_id','admin_status','oper_status','in_bps','out_bps','in_utilization_pct','out_utilization_pct','rate_status','speed_bps')},
          f"{ident} administrative status {s['admin_status']}, operational status {s['oper_status']}.",90)
        latest[ident]=item
    probes=defaultdict(list);probe_facts={}
    for p in sorted(bundle['probes'],key=lambda p:p['observed_at'],reverse=True):
        probes[p['device_id']].append(p)
        probe_facts[p['probe_id']]=add('probe:'+p['probe_id'],p['device_id'],'probe',p['observed_at'],'icmp',
          {'status':p['status'],'source_ip':p['source_ip'],'rtt_ms':p['rtt_ms']},f"ICMP probe returned {p['status']}.",30)
    snapshots=defaultdict(list);console={};ospf={};acl={};configfacts={}
    baseline_path=Path(__file__).with_name('baseline.json')
    baseline=json.loads(baseline_path.read_text()) if baseline_path.exists() else {'snapshots':[]}
    baseline_snapshots={s['device_id']:s for s in baseline['snapshots']}
    for s in sorted(bundle['snapshots'],key=lambda s:s['observed_at'],reverse=True):snapshots[s['device_id']].append(s)
    for device,items in snapshots.items():
        s=items[0];addresses=command(s,'addresses')
        if addresses is not None:
            for addr in addresses:
                name=addr['ifname']
                console[device+':'+name]=add('snapshot:'+s['snapshot_id']+':link:'+name,device,'console_interface',s['observed_at'],s['source'],
                  {'interface':name,'admin_up':'UP' in addr['flags'],'operstate':addr['operstate'],'addresses':addr.get('addr_info',[])},
                  f"Console shows {name} administratively {'up' if 'UP' in addr['flags'] else 'down'}.",100)
        ns=command(s,'ospf_neighbors')
        if ns is not None:
            ospf[device]=add('snapshot:'+s['snapshot_id']+':ospf',device,'ospf_neighbors',s['observed_at'],s['source'],ns,
              'Read-only FRR OSPF neighbor snapshot.',100)
        rules=command(s,'acl')
        if rules is not None:
            acl[device]=add('snapshot:'+s['snapshot_id']+':acl',device,'acl',s['observed_at'],s['source'],rules,
              'Read-only nftables rules and counters.',100)
        if devices[device]['role'] in ('router','mls'):
            for dev,iface in ports:
                if dev!=device:continue
                mode=ospf_mode(s,iface);reference=baseline_snapshots.get(device)
                expected=ospf_mode(reference,iface) if reference else None
                if mode is None:continue
                configfacts[device+':'+iface]=add('snapshot:'+s['snapshot_id']+':ospf_config:'+iface,device,'ospf_config',s['observed_at'],s['source'],
                  {'interface':iface,'observed_mode':mode,'baseline_mode':expected,'baseline_snapshot_id':reference['snapshot_id'] if reference else None},
                  f"OSPF interface {iface} is {mode}; verified healthy reference mode is {expected or 'unavailable'}.",100)
    events=[]
    for e in bundle['events']:
        if e['parse_error'] or e['identity_status']!='source_and_hostname':continue
        message=e['message'];kind='routing_event';interface=None
        m=re.search(r'\b(eth\d+):\s*<([^>]+)>.*\bstate (\w+)\b',message)
        if e['program']=='link-state' and m:kind='link_up' if 'UP' in m[2].split(',') else 'link_down';interface=m[1]
        elif e['program']=='ospfd' and re.search(r'Full\s*->\s*(Deleted|Down|Init)',message,re.I):
            kind='ospf_loss_event';m=re.search(r' on (eth\d+)',message);interface=m[1] if m else None
        else:continue
        events.append(add('event:'+e['event_id'],e['device_id'],kind,e['received_at'],'syslog',
          {'interface':interface,'program':e['program'],'raw_message':message},
          f"Identified {e['program']} event: {kind} on {interface or 'unspecified interface'}.",150))
    candidates={}
    def candidate(kind,device,interface=None):
        fingerprint='|'.join((kind,device,interface or ''))
        if fingerprint not in candidates:
            candidates[fingerprint]={'fingerprint':fingerprint,'fault_class':kind,'device_id':device,'interface':interface,
              'site':devices[device]['site'],'signals':defaultdict(list),'contradictions':[],'rules_applied':[],
              'affected_devices':[],'related_evidence_ids':[],'topology_path':path(device)}
        return candidates[fingerprint]
    def signal(c,name,*items):
        for item in items:
            if usable(item):c['signals'][name].append(item['evidence_id'])
    def failed(device):
        ps=probes[device]
        return len(ps)>=2 and all(p['status']=='timeout' and usable(probe_facts[p['probe_id']]) for p in ps[:2])
    def current_probe(device):
        return probe_facts[probes[device][0]['probe_id']] if probes[device] else None
    # R1: a state observation identifies a linked physical interface, not an
    # unused ovs-netdev/internal interface that is normally down.
    for device,name in sorted(ports):
        ident=device+':'+name;s=latest.get(ident);co=console.get(ident)
        down=usable(s) and s['value']['admin_status']==2
        console_down=usable(co) and not co['value']['admin_up']
        if not (down or console_down):continue
        c=candidate('interface_shutdown',device,name);c['rules_applied'].append('R1_LINKED_INTERFACE_DOWN')
        if down:signal(c,'interface_down',s)
        if console_down:signal(c,'interface_down',co);signal(c,'console_down',co)
        if down and usable(co) and s['value']['admin_status']==2 and co['value']['admin_up']:
            c['contradictions'].append('SNMP admin-down conflicts with a fresh console admin-up observation')
        if usable(s) and console_down and s['value']['admin_status']==1:
            c['contradictions'].append('Fresh SNMP admin-up conflicts with console admin-down; wait for a consistent observation window')
        for e in events:
            if e['device_id']==device and e['value']['interface']==name and e['kind']=='link_down':signal(c,'link_event',e)
            if usable(e) and e['device_id']==device and e['value']['interface']==name and e['kind']=='ospf_loss_event':
                c['related_evidence_ids'].append(e['evidence_id']);c['rules_applied'].append('R2_OSPF_EVENT_ON_SAME_INTERFACE')
        # Topology-dependent failures must be on the path that contains this
        # exact failed interface, not just anywhere in the same branch.
        for target in devices:
            p=path(target)
            pairs=list(zip(p,p[1:]))
            affected=any((a==device and edge.get((a,b))==name) or (b==device and edge.get((b,a))==name) for a,b in pairs)
            if affected and failed(target):
                c['affected_devices'].append(target);signal(c,'downstream_failure',current_probe(target))
        if c['affected_devices']:c['rules_applied'].append('R2_TOPOLOGY_DEPENDENT_PROBE_FAILURES')
    # R3: required point-to-point neighbors are derived from topology and
    # observed /30 addresses. Broadcast 2-Way/DROther is valid, not a fault.
    for link in bundle['links']:
        if link['purpose']!='Routed /30 uplink':continue
        for a,b,iface in ((link['a_device'],link['b_device'],link['a_interface']),
                          (link['b_device'],link['a_device'],link['b_interface'])):
            n=ospf.get(a);co=console.get(a+':'+iface)
            if not usable(n) or not usable(co):continue
            nets=[ipaddress.ip_interface(v['local']+'/'+str(v['prefixlen'])).network for v in co['value']['addresses'] if v['family']=='inet' and v['prefixlen']==30]
            expected={ip for ip in devices[b]['aliases'] if any(ipaddress.ip_address(ip) in net for net in nets)}
            observed={v.get('address') for v in neighbors(n['value'])}
            if not expected or expected & observed:continue
            # Underlying link-down evidence belongs to R1; retain OSPF as a
            # symptom in the event trace instead of producing a second cause.
            if not co['value']['admin_up'] or any((c['device_id']==a and c['interface']==iface) or a in c['affected_devices'] for c in candidates.values()):continue
            c=candidate('ospf_loss',a,iface);c['rules_applied'].append('R3_EXPECTED_P2P_NEIGHBOR_ABSENT')
            c['expected_neighbors']=sorted(expected)
            signal(c,'underlying_link_up',co)
            # A recovering link can be up before OSPF converges. Require two
            # missing-neighbor snapshots with the interface up across the
            # interval, and never recycle an event that preceded a link-up.
            previous=snapshots[a][1] if len(snapshots[a])>1 else None
            prior_neighbors=command(previous,'ospf_neighbors') if previous else None
            prior_addresses=command(previous,'addresses') if previous else None
            stable=previous and prior_neighbors is not None and prior_addresses is not None and \
              MATRIX['minimum_snapshot_separation_seconds']<=(dt(n['observed_at'])-dt(previous['observed_at'])).total_seconds()<=MATRIX['freshness_seconds']['snapshot'] and \
              not (expected & {v.get('address') for v in neighbors(prior_neighbors)}) and \
              any(v['ifname']==iface and 'UP' in v['flags'] for v in prior_addresses)
            up_events=[e for e in events if usable(e) and e['device_id']==a and e['kind']=='link_up' and e['value']['interface']==iface]
            latest_up=max((dt(e['observed_at']) for e in up_events),default=None)
            grace=latest_up is not None and (at-latest_up).total_seconds()<MATRIX['link_recovery_grace_seconds']
            if stable and not grace:
                signal(c,'neighbor_loss',n)
                prior=add('snapshot:'+previous['snapshot_id']+':ospf',a,'ospf_neighbors',previous['observed_at'],previous['source'],prior_neighbors,'Previous missing-neighbor observation with underlying interface up.',100)
                signal(c,'neighbor_loss',prior);c['rules_applied'].append('R3_STABLE_LOSS_ACROSS_TWO_SNAPSHOTS')
            for e in events:
                if e['device_id']==a and e['kind']=='ospf_loss_event' and e['value']['interface']==iface and (latest_up is None or dt(e['observed_at'])>latest_up):signal(c,'ospf_event',e)
            config=configfacts.get(a+':'+iface)
            if usable(config) and config['value']['baseline_mode']=='active' and config['value']['observed_mode']=='passive':
                signal(c,'configuration_change',config);c['rules_applied'].append('R3_OBSERVED_OSPF_PASSIVITY_CHANGE')
            for target in devices:
                route=path(target)
                if any((x==a and edge.get((x,y))==iface) or (y==a and edge.get((y,x))==iface) for x,y in zip(route,route[1:])) and failed(target):c['affected_devices'].append(target)
    # R4: repeated failures are a symptom class; upstream evidence does not
    # establish that a device is powered off or any other unseen cause.
    for device in devices:
        if not failed(device):continue
        if any(device in c['affected_devices'] for c in candidates.values()):continue
        c=candidate('unreachability',device);c['rules_applied'].append('R4_REPEATED_PROBE_FAILURE')
        signal(c,'repeated_probe_failure',*(probe_facts[p['probe_id']] for p in probes[device][:2]))
        upstream=parent.get(device)
        if upstream:
            signal(c,'upstream_status',latest.get(upstream+':'+edge[(upstream,device)]),console.get(upstream+':'+edge[(upstream,device)]))
        signal(c,'fresh_poll_outcome',pollfacts.get(device))
        if upstream:
            # The topology fact has its own source and export timestamp.
            t=add('topology:'+digest(path(device))[:16],device,'topology',bundle['as_of'],'inventory',{'path':path(device)},'Inventory path from monitoring server to target.',100)
            signal(c,'topology_path',t)
    # R5: sustained utilization needs three measured intervals AND a configured
    # effective capacity. A nominal virtual NIC speed cannot satisfy the gate.
    interface_meta={i['interface_id']:i for i in bundle['interfaces']}
    for ident,series in history.items():
        meta=interface_meta.get(ident)
        if meta is None:continue
        if (meta['device_id'],meta['name']) not in ports or len(series)<3:continue
        samples=series[:3]
        if not all(s['rate_status']=='valid' and max(s.get('in_utilization_pct') or 0,s.get('out_utilization_pct') or 0)>=80 for s in samples):continue
        if not all(0<=(at-dt(s['observed_at'])).total_seconds()<=100 for s in samples):continue
        c=candidate('high_utilization',meta['device_id'],meta['name']);c['rules_applied'].append('R5_THREE_SUSTAINED_RATE_INTERVALS')
        for s in samples:
            f=add('rate:'+s['poll_id']+':'+ident,s['device_id'],'rate',s['observed_at'],'snmp',
              {k:s[k] for k in ('in_bps','out_bps','speed_bps','interval_s','in_utilization_pct','out_utilization_pct')},
              (f"Measured {s['device_id']} {meta['name']} traffic: ingress {s['in_bps']:.0f} bps, egress {s['out_bps']:.0f} bps. "+(f"Configured effective capacity {s['speed_bps']} bps; utilization at least 80 percent." if meta['capacity_source']=='configured_effective_capacity' else 'Effective capacity reference is unavailable; utilization cannot be independently verified.')),100)
            signal(c,'sustained_rates',f);signal(c,'fresh_counters',f)
        if meta['capacity_source']=='configured_effective_capacity':signal(c,'effective_capacity',latest[ident])
    # ACL handling is deliberately exact-match and fail-closed. Unsupported nft
    # expressions do not provide distinguishing evidence.
    for device,ps in probes.items():
        if not failed(device):continue
        source=ps[0]['source_ip'];target=devices[device].get('management_ip')
        for node in path(device):
            a=acl.get(node)
            if not usable(a) or not target:continue
            previous=command(snapshots[node][1],'acl') if len(snapshots[node])>1 else None
            old={r['rule']['handle']:r['rule'] for r in (previous or {}).get('nftables',[]) if 'rule' in r}
            for obj in a['value'].get('nftables',[]):
                if 'rule' not in obj:continue
                rule=obj['rule'];expr=rule.get('expr',[]);matched=True;packets=None;drop=False
                p=path(device);incoming=edge.get((node,p[p.index(node)-1])) if p.index(node)>0 else None
                for clause in expr:
                    if 'counter' in clause:packets=clause['counter']['packets'];continue
                    if 'drop' in clause:drop=True;continue
                    m=clause.get('match',{});left=m.get('left',{});right=m.get('right')
                    if m.get('op')!='==':matched=False;break
                    if left.get('meta',{}).get('key')=='iifname':matched &= right==incoming
                    elif left.get('payload',{}).get('protocol')=='ip' and left['payload'].get('field') in ('saddr','daddr'):
                        ip=source if left['payload']['field']=='saddr' else target
                        try:
                            net=(right['prefix']['addr']+'/'+str(right['prefix']['len'])) if isinstance(right,dict) else right
                            matched &= ipaddress.ip_address(ip) in ipaddress.ip_network(net,strict=False)
                        except (ValueError,KeyError,TypeError):matched=False
                    else:matched=False
                prior=old.get(rule['handle']);delta=None
                if prior and [e for e in prior['expr'] if 'counter' not in e]==[e for e in expr if 'counter' not in e]:
                    previous_packets=next((e['counter']['packets'] for e in prior['expr'] if 'counter' in e),None)
                    if previous_packets is not None and packets is not None:delta=packets-previous_packets
                if not (matched and drop):continue
                c=candidate('acl_fault',node);c['rules_applied'].append('R6_EXACT_MONITOR_FLOW_MATCHES_DENY_RULE')
                c['affected_devices'].append(device);signal(c,'failed_flow',current_probe(device));signal(c,'matching_rule',a)
                if delta is not None and delta>0:
                    f=add('acl-delta:'+a['evidence_id']+':'+str(rule['handle']),node,'acl_counter_delta',a['observed_at'],a['source'],
                      {'handle':rule['handle'],'packets_delta':delta,'source':source,'destination':target},'Matching deny counter increased between two snapshots.',100)
                    signal(c,'deny_counter_delta',f)
                cp=current_probe(node)
                if usable(cp) and cp['value']['status']=='ok':signal(c,'upstream_healthy',cp)
    result=[]
    for c in candidates.values():
        c['gate']=evaluate_gate(c['fault_class'],c.pop('signals'),c.pop('contradictions'))
        ids={i for group in c['gate']['signals'].values() for i in group}
        ids.update(c['related_evidence_ids'])
        c['facts']=[by_id[i] for i in sorted(ids)]
        c['missing_observations']=c['gate']['missing'];c['as_of']=bundle['as_of']
        c['evidence_digest']=digest({'facts':c['facts'],'gate':c['gate']})
        result.append(c)
    health=[]
    for device,d in devices.items():
        if d['role']=='monitor':state='healthy'
        else:
            p=current_probe(device);poll=pollfacts.get(device)
            if not usable(p) or (d['monitored'] and not usable(poll)):state='unknown'
            elif p['value']['status']!='ok' or (d['monitored'] and poll['value']['status']!='ok'):state='unreachable'
            else:state='healthy'
        health.append({'device_id':device,'site':d['site'],'role':d['role'],'management_ip':d['management_ip'],'state':state})
    attributed={d for c in result if c['fault_class'] in ('interface_shutdown','ospf_loss','acl_fault') and c['gate']['status']=='sufficient' for d in c['affected_devices']}
    result=[c for c in result if not (c['fault_class']=='unreachability' and c['device_id'] in attributed)]
    return {'as_of':bundle['as_of'],'incidents':result,'health':health,'facts':facts,
      'links':bundle['links'],'heartbeats':bundle['heartbeats'],'counts':bundle['counts'],'matrix':MATRIX,
      'coverage':{'signals_implemented':list(MATRIX['faults']),'capacity_calibration_required':True}}
