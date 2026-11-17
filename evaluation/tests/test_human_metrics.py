import unittest
from evaluation.human_metrics import aggregate,kappa
class HumanMetricTests(unittest.TestCase):
    def test_perfect_varied_ratings(self):self.assertEqual(kappa([1,3,5],[1,3,5],[1,2,3,4,5])['kappa'],1)
    def test_opposed_ratings(self):self.assertAlmostEqual(kappa([1,2,1,2],[2,1,2,1],[1,2])['kappa'],-1)
    def test_constant_agreement_is_undefined(self):
        r=kappa(['confirm']*3,['confirm']*3);self.assertIsNone(r['kappa']);self.assertEqual(r['exact_agreement'],1)
    def test_zero_denominator_is_missing_not_zero(self):
        r=aggregate([]);self.assertIsNone(r['unsupported_claim_rate']);self.assertIsNone(r['read_only_recommendation_rate'])
    def test_rates_use_claim_and_recommendation_denominators(self):
        r={'claim_count':4,'unsupported_claim_count':1,'recommendation_count':2,'relevant_recommendation_count':1,'read_only_recommendation_count':2,'supported_recommendation_count':1,'usefulness_1_to_5':3,'evidence_support_1_to_5':4}
        a=aggregate([r]);self.assertEqual(a['unsupported_claim_rate'],.25);self.assertEqual(a['read_only_recommendation_rate'],1)
if __name__=='__main__':unittest.main()
