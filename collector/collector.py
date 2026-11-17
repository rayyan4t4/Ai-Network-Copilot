"""Week 1 evidence collection. No diagnosis, configuration writes or fault labels."""
import concurrent.futures
import contextlib
import ipaddress
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime,timezone
from pathlib import Path
import psycopg2
from psycopg2.extras import Json,RealDictCursor
from rates import calculate_rates

VERSION='week1.1'
CONFIG=json.loads(Path(os.environ.get('COPILOT_CONFIG','/etc/fyp/collector.json')).read_text())
INVENTORY=json.loads(Path(CONFIG['inventory_file']).read_text())
STOP=threading.Event()
SNMP_BASE='.1.3.6.1.2.1.2.2.1.'
IFX_BASE='.1.3.6.1.2.1.31.1.1.1.'
LOG=logging.getLogger('copilot.collector')

def now():return datetime.now(timezone.utc)
@contextlib.contextmanager
def database():
    connection=psycopg2.connect(CONFIG['database'],connect_timeout=5)
    try:
        with connection:yield connection
    finally:connection.close()

def initialize_inventory():
    with database() as conn,conn.cursor() as cur:
        for name,spec in INVENTORY['nodes'].items():
            aliases=[spec.get('management_ip') or spec.get('expected_ip')]
            site=next((s for s in INVENTORY['sites'] if s['name']==spec.get('site')),None)
            if spec['role']=='router':aliases.append(site['transit']+'.1')
            if spec['role']=='mls':
                aliases.append(site['transit']+'.2')
                aliases.extend('192.168.'+str(sub)+'.1' for sub in site['vlans'].values())
            aliases=sorted(set(a for a in aliases if a))
            monitored=spec['role'] not in ('host','monitor')
            cur.execute('''INSERT INTO inventory.devices(device_id,hostname,site,role,management_ip,aliases,monitored,metadata)
              VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(device_id) DO UPDATE SET
              management_ip=excluded.management_ip,aliases=excluded.aliases,monitored=excluded.monitored,metadata=excluded.metadata''',
              (name,name,spec.get('site','WAN'),spec['role'],aliases[0] if not spec.get('management_ip') else spec['management_ip'],Json(aliases),monitored,Json(spec)))
        for link in INVENTORY['links']:
            identity=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(link,sort_keys=True)))
            cur.execute('''INSERT INTO inventory.links VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                (identity,link['a'],'eth'+str(link['a_port']),link['b'],'eth'+str(link['b_port']),link['purpose']))

def heartbeat(service,status,detail):
    with database() as conn,conn.cursor() as cur:
        cur.execute('''INSERT INTO operations.heartbeats(service,status,detail) VALUES(%s,%s,%s)
         ON CONFLICT(service) DO UPDATE SET updated_at=clock_timestamp(),status=excluded.status,detail=excluded.detail''',(service,status,Json(detail)))

class ObservationError(Exception):pass
def snmp(device,kind,oids):
    args=[kind,'-m','','-On','-Oe','-v2c','-c',CONFIG['snmp_community'],'-t','0.7','-r','0']
    if kind=='snmpbulkwalk':args+=['-Cr20']
    args+=[device['management_ip']]+oids
    try:reply=subprocess.run(args,capture_output=True,text=True,timeout=8)
    except subprocess.TimeoutExpired:raise ObservationError('SNMP request timed out') from None
    text=reply.stdout
    if reply.returncode:
        detail=(reply.stderr or text).replace(CONFIG['snmp_community'],'[redacted]')[:1024]
        raise ObservationError(detail or 'SNMP request failed')
    return {line.split(' = ',1)[0].strip():line.split(' = ',1)[1].strip() for line in text.splitlines() if ' = ' in line}

def number(value):
    if value is None or 'No Such' in value:return None
    value=value.split(':',1)[-1].strip()
    ticks=re.match(r'\((\d+)\)',value)
    if ticks:return int(ticks.group(1))
    match=re.match(r'(-?\d+)',value)
    return int(match.group(1)) if match else None
def string(value):
    return value.split(':',1)[-1].strip().strip('"') if value else None

def poll_device(device):
    started=now();poll_id=str(uuid.uuid4());raw={};status='ok';error=None
    try:
        raw.update(snmp(device,'snmpget',['.1.3.6.1.2.1.1.3.0','.1.3.6.1.2.1.1.5.0','.1.3.6.1.4.1.2021.4.5.0','.1.3.6.1.4.1.2021.4.6.0']))
        raw.update(snmp(device,'snmpbulkwalk',[SNMP_BASE[:-1]]))
        raw.update(snmp(device,'snmpbulkwalk',[IFX_BASE[:-1]]))
        if not any(key.startswith(SNMP_BASE+'8.') for key in raw):
            raise ObservationError('Required interface-state table is missing')
    except ObservationError as problem:
        error=str(problem);status='timeout' if 'time' in error.lower() else 'error'
    uptime=number(raw.get('.1.3.6.1.2.1.1.3.0'))
    with database() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('INSERT INTO telemetry.polls(poll_id,device_id,observed_at,status,error,raw,collector_version) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                    (poll_id,device['device_id'],started,status,error,Json(raw),VERSION))
        if status!='ok':return status
        cur.execute('INSERT INTO telemetry.device_health(poll_id,sysuptime_ticks,reported_name,memory_total_kib,memory_available_kib) VALUES(%s,%s,%s,%s,%s)',
            (poll_id,uptime,string(raw.get('.1.3.6.1.2.1.1.5.0')),number(raw.get('.1.3.6.1.4.1.2021.4.5.0')),number(raw.get('.1.3.6.1.4.1.2021.4.6.0'))))
        indices=sorted({int(oid[len(SNMP_BASE):].split('.')[1]) for oid in raw if oid.startswith(SNMP_BASE)})
        for index in indices:
            def value(column,extended=False):return raw.get((IFX_BASE if extended else SNMP_BASE)+str(column)+'.'+str(index))
            name=string(value(1,True)) or string(value(2)) or 'ifindex-'+str(index)
            identity=device['device_id']+':'+name
            hc_in,hc_out=number(value(6,True)),number(value(10,True))
            bits=64 if hc_in is not None and hc_out is not None else 32
            speed=number(value(5))
            high=number(value(15,True))
            if high and high>0:speed=high*1000000
            override=CONFIG.get('capacity_overrides_bps',{}).get(identity)
            if override:speed=int(override)
            if speed is not None and speed<=0:speed=None
            current={'ifindex':index,'observed_at':started,'in_octets':hc_in if bits==64 else number(value(10)),
                'out_octets':hc_out if bits==64 else number(value(16)),'counter_bits':bits,'speed_bps':speed,
                'sysuptime_ticks':uptime,'discontinuity_ticks':number(value(19,True))}
            cur.execute('SELECT * FROM telemetry.interface_samples WHERE interface_id=%s ORDER BY observed_at DESC LIMIT 1',(identity,))
            previous=cur.fetchone()
            if previous:
                for key in ('in_octets','out_octets'):
                    if previous[key] is not None:previous[key]=int(previous[key])
            rates=calculate_rates(current,previous)
            cur.execute('''INSERT INTO inventory.interfaces VALUES(%s,%s,%s,%s,%s,%s)
              ON CONFLICT(interface_id) DO UPDATE SET current_ifindex=excluded.current_ifindex,capacity_bps=excluded.capacity_bps,capacity_source=excluded.capacity_source''',
              (identity,device['device_id'],name,index,speed,'configured_effective_capacity' if override else 'snmp'))
            fields=['poll_id','interface_id','observed_at','ifindex','admin_status','oper_status','in_octets','out_octets','in_errors','out_errors','counter_bits','speed_bps','sysuptime_ticks','discontinuity_ticks','interval_s','in_bps','out_bps','in_utilization_pct','out_utilization_pct','rate_status']
            row={'poll_id':poll_id,'interface_id':identity,**current,**rates,'admin_status':number(value(7)),'oper_status':number(value(8)),
                 'in_errors':number(value(14)),'out_errors':number(value(20))}
            cur.execute('INSERT INTO telemetry.interface_samples('+','.join(fields)+') VALUES('+','.join(['%s']*len(fields))+')',[row[f] for f in fields])
    return status

def probe_device(device):
    started=now();status='error';rtt=None
    try:
        reply=subprocess.run(['ping','-n','-c','1','-W','1',device['management_ip']],capture_output=True,text=True,timeout=3)
        raw=reply.stdout+reply.stderr;status='ok' if reply.returncode==0 else ('timeout' if reply.returncode==1 else 'error')
        match=re.search(r'time[=<]([0-9.]+)\s*ms',raw)
        if match:rtt=float(match.group(1))
    except subprocess.TimeoutExpired:raw='Probe command timed out';status='timeout'
    with database() as conn,conn.cursor() as cur:
        cur.execute('INSERT INTO telemetry.probes(probe_id,device_id,observed_at,source_ip,status,rtt_ms,raw) VALUES(%s,%s,%s,%s,%s,%s,%s)',
            (str(uuid.uuid4()),device['device_id'],started,'192.168.30.10',status,rtt,raw[:4096]))
    return status

def devices(monitored=False):
    with database() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT device_id,host(management_ip) management_ip,hostname,aliases FROM inventory.devices WHERE management_ip IS NOT NULL'+(' AND monitored' if monitored else " AND role!='monitor'"))
        return cur.fetchall()

def cycle_loop(service,interval,worker,monitored):
    while not STOP.is_set():
        began=time.monotonic()
        try:
            targets=devices(monitored)
            with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG['workers']) as pool:
                states=list(pool.map(worker,targets))
            heartbeat(service,'ok',{'targets':len(targets),'observed_ok':states.count('ok'),'observed_unavailable':len(states)-states.count('ok'),'elapsed_s':round(time.monotonic()-began,3)})
        except Exception:
            LOG.exception('%s cycle failed',service)
            try:heartbeat(service,'error',{'message':'cycle failed; see collector log'})
            except Exception:pass
        STOP.wait(max(1,interval-(time.monotonic()-began)))

def parse_time(value):
    if not isinstance(value,str) or not value:return None
    try:
        t=datetime.fromisoformat(value.replace('Z','+00:00'))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (TypeError,ValueError):return None

def ingest_syslog():
    path=Path(CONFIG['syslog_file'])
    if not path.exists():return 0
    stat=path.stat();identity=f'{stat.st_dev}:{stat.st_ino}'
    with database() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute('SELECT pg_advisory_xact_lock(%s)',(8427011,))
        cur.execute('SELECT * FROM operations.checkpoints WHERE service=%s FOR UPDATE',('syslog',));checkpoint=cur.fetchone()
        if checkpoint and checkpoint['file_identity']==identity and stat.st_size>=checkpoint['byte_offset']:
            generation=str(checkpoint['generation']);offset=checkpoint['byte_offset']
        else:generation=str(uuid.uuid4());offset=0
        cur.execute('SELECT device_id,hostname,aliases FROM inventory.devices');known={d['hostname']:d for d in cur.fetchall()}
        count=0
        with path.open('rb') as stream:
            stream.seek(offset)
            for _ in range(500):
                start=stream.tell();line=stream.readline()
                if not line or not line.endswith(b'\n'):break
                raw=line.decode(errors='replace').rstrip('\n');parse_error=None
                try:
                    data=json.loads(raw)
                    if not isinstance(data,dict):data={};parse_error='Syslog JSON must be an object'
                except (ValueError,TypeError):data={};parse_error='Malformed JSON syslog line'
                hostname=str(data.get('hostname') or '').strip();device=known.get(hostname)
                source=data.get('source_ip')
                try:source=str(ipaddress.ip_address(source))
                except (ValueError,TypeError):source=None
                identity_state='source_and_hostname' if device and source in device['aliases'] else ('hostname_only' if device else 'unknown')
                severity=data.get('severity')
                try:severity=int(severity)
                except (ValueError,TypeError):severity=None
                if severity is not None and not 0<=severity<=7:severity=None
                event_id=str(uuid.uuid5(uuid.UUID(generation),str(start)))
                cur.execute('''INSERT INTO telemetry.syslog_events(event_id,device_id,event_time,received_at,source_ip,reported_hostname,program,severity,message,raw,identity_status,parse_error,file_generation,byte_offset)
                  VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                  (event_id,device['device_id'] if device else None,parse_time(data.get('event_time')),parse_time(data.get('received_at')) or now(),source,hostname or None,str(data.get('program') or ''),severity,str(data.get('message',raw)),str(data.get('raw',raw)),identity_state,parse_error,generation,start))
                offset=stream.tell();count+=1
        cur.execute('''INSERT INTO operations.checkpoints(service,file_identity,generation,byte_offset) VALUES(%s,%s,%s,%s)
         ON CONFLICT(service) DO UPDATE SET file_identity=excluded.file_identity,generation=excluded.generation,byte_offset=excluded.byte_offset,updated_at=clock_timestamp()''',('syslog',identity,generation,offset))
    return count

def syslog_loop():
    while not STOP.is_set():
        try:heartbeat('syslog','ok',{'ingested':ingest_syslog()})
        except Exception:LOG.exception('Syslog ingestion failed')
        STOP.wait(2)

def status():
    queries={
      'counts':"SELECT (SELECT count(*) FROM inventory.devices) devices,(SELECT count(*) FROM inventory.links) links,(SELECT count(*) FROM inventory.interfaces) interfaces,(SELECT count(*) FROM telemetry.polls) polls,(SELECT count(*) FROM telemetry.interface_samples) samples,(SELECT count(*) FROM telemetry.probes) probes,(SELECT count(*) FROM telemetry.syslog_events) events",
      'heartbeats':"SELECT service,updated_at,status,detail FROM operations.heartbeats ORDER BY service",
      'latest_polls':"SELECT device_id,status,observed_at,is_stale FROM telemetry.latest_polls ORDER BY device_id",
      'latest_probes':"SELECT device_id,status,observed_at,is_stale FROM telemetry.latest_probes ORDER BY device_id"}
    answer={}
    with database() as conn,conn.cursor(cursor_factory=RealDictCursor) as cur:
        for key,query in queries.items():cur.execute(query);answer[key]=cur.fetchall()
    print(json.dumps(answer,default=str,indent=2))

def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    action=sys.argv[1] if len(sys.argv)>1 else 'run'
    if action=='inventory':initialize_inventory();return
    if action=='status':status();return
    if action=='ingest-once':print(ingest_syslog());return
    if action=='poll-once':
        for d in devices(True):print(d['device_id'],poll_device(d),flush=True)
        return
    if action=='probe-once':
        for d in devices():print(d['device_id'],probe_device(d),flush=True)
        return
    if action!='run':raise SystemExit('Unknown command')
    signal.signal(signal.SIGTERM,lambda *_:STOP.set());signal.signal(signal.SIGINT,lambda *_:STOP.set())
    threads=[threading.Thread(target=cycle_loop,args=('snmp',CONFIG['poll_interval_seconds'],poll_device,True)),
             threading.Thread(target=cycle_loop,args=('probes',CONFIG['probe_interval_seconds'],probe_device,False)),threading.Thread(target=syslog_loop)]
    for thread in threads:thread.start()
    for thread in threads:thread.join()

if __name__=='__main__':main()
