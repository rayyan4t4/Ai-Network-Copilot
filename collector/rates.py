"""Counter-derived rates with explicit invalid/missing/reset outcomes."""
MAX_GAP_SECONDS=120

def counter_delta(current, previous, bits, seconds, capacity):
    if current is None or previous is None:return None,'missing_counter'
    if bits==32 and capacity and capacity*seconds>=2**32*8:
        return None,'ambiguous_multiple_wraps'
    if current>=previous:return current-previous,'valid'
    if bits!=32:return None,'counter_reset'
    wrapped=current+2**32-previous
    if not capacity or wrapped*8/seconds>capacity*1.2:return None,'counter_reset_or_wrap_unknown'
    return wrapped,'valid_wrapped'

def calculate_rates(current,previous):
    result={'interval_s':None,'in_bps':None,'out_bps':None,
            'in_utilization_pct':None,'out_utilization_pct':None,'rate_status':'warmup'}
    if not previous:return result
    seconds=(current['observed_at']-previous['observed_at']).total_seconds()
    result['interval_s']=seconds
    if seconds<=0:result['rate_status']='invalid_interval';return result
    if seconds>MAX_GAP_SECONDS:result['rate_status']='stale_previous';return result
    if current['ifindex']!=previous['ifindex'] or current['counter_bits']!=previous['counter_bits']:
        result['rate_status']='interface_reindexed';return result
    for key in ('discontinuity_ticks',):
        if current.get(key)!=previous.get(key):result['rate_status']='counter_discontinuity';return result
    a,b=current.get('sysuptime_ticks'),previous.get('sysuptime_ticks')
    if a is not None and b is not None and a<b and not (b>2**32-360000 and a<360000):
        result['rate_status']='agent_restart';return result
    statuses=[]
    capacity=current.get('speed_bps')
    for direction in ('in','out'):
        delta,status=counter_delta(current.get(direction+'_octets'),previous.get(direction+'_octets'),current['counter_bits'],seconds,capacity)
        statuses.append(status)
        if delta is not None:
            bps=delta*8/seconds;result[direction+'_bps']=bps
            if capacity and capacity>0:result[direction+'_utilization_pct']=100*bps/capacity
    result['rate_status']='valid' if all(s=='valid' for s in statuses) else ','.join(statuses)
    return result
