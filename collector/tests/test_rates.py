import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rates import calculate_rates

class CounterRateTests(unittest.TestCase):
    def sample(self,**overrides):
        sample={'observed_at':datetime(2026,11,16,tzinfo=timezone.utc),'ifindex':2,'counter_bits':64,'speed_bps':1000000,'sysuptime_ticks':1000,'discontinuity_ticks':0,'in_octets':1000,'out_octets':2000}
        sample.update(overrides);return sample
    def later(self,previous,**overrides):
        return {**previous,'observed_at':previous['observed_at']+timedelta(seconds=10),'sysuptime_ticks':2000,**overrides}
    def test_known_rate_and_utilization(self):
        old=self.sample();result=calculate_rates(self.later(old,in_octets=126000),old)
        self.assertEqual(result['in_bps'],100000)
        self.assertEqual(result['in_utilization_pct'],10)
    def test_32_bit_wrap_is_not_negative(self):
        old=self.sample(counter_bits=32,in_octets=2**32-50)
        result=calculate_rates(self.later(old,in_octets=50),old)
        self.assertEqual(result['in_bps'],80)
        self.assertIn('wrapped',result['rate_status'])
    def test_64_bit_decrease_is_not_wrap(self):
        old=self.sample();result=calculate_rates(self.later(old,in_octets=50),old)
        self.assertIsNone(result['in_bps'])
        self.assertIn('counter_reset',result['rate_status'])
    def test_restart_invalidates_rates(self):
        old=self.sample();result=calculate_rates(self.later(old,sysuptime_ticks=5),old)
        self.assertEqual(result['rate_status'],'agent_restart')
    def test_reindex_invalidates_rates(self):
        old=self.sample();self.assertEqual(calculate_rates(self.later(old,ifindex=9),old)['rate_status'],'interface_reindexed')
    def test_stale_gap_invalidates_rates(self):
        old=self.sample();new=self.later(old,observed_at=old['observed_at']+timedelta(seconds=180))
        self.assertEqual(calculate_rates(new,old)['rate_status'],'stale_previous')
    def test_missing_capacity_keeps_rate_but_not_percentage(self):
        old=self.sample(speed_bps=None);r=calculate_rates(self.later(old,in_octets=2000),old)
        self.assertEqual(r['in_bps'],800);self.assertIsNone(r['in_utilization_pct'])
    def test_missing_counter_stays_missing(self):
        old=self.sample();r=calculate_rates(self.later(old,in_octets=None),old)
        self.assertIsNone(r['in_bps'])
    def test_discontinuity_invalidates_rates(self):
        old=self.sample();self.assertEqual(calculate_rates(self.later(old,discontinuity_ticks=500),old)['rate_status'],'counter_discontinuity')
    def test_possible_multiple_32_bit_wraps_are_ambiguous(self):
        old=self.sample(counter_bits=32,speed_bps=10000000000)
        self.assertIn('ambiguous_multiple_wraps',calculate_rates(self.later(old,in_octets=2000),old)['rate_status'])

if __name__=='__main__':unittest.main()
