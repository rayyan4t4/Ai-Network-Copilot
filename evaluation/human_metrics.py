"""Statistics for supplied human judgments; never generate judgments."""
from collections import Counter
def fraction(n,d):return n/d if d else None
def kappa(left,right,levels=None):
    if len(left)!=len(right) or not left:raise ValueError('Paired nonempty ratings required')
    labels=levels or sorted(set(left)|set(right));index={v:i for i,v in enumerate(labels)}
    if any(x not in index for x in left+right):raise ValueError('Unknown rating')
    def distance(a,b):return abs(index[a]-index[b])/(len(labels)-1) if levels and len(labels)>1 else int(a!=b)
    n=len(left);a=Counter(left);b=Counter(right);observed=sum(distance(x,y) for x,y in zip(left,right))/n
    expected=sum(a[x]*b[y]*distance(x,y) for x in labels for y in labels)/(n*n)
    return {'paired_n':n,'exact_agreement':sum(x==y for x,y in zip(left,right))/n,'kappa':1-observed/expected if expected else None,'weighting':'linear ordinal' if levels else 'unweighted nominal','undefined_if_no_expected_disagreement':not bool(expected)}
def aggregate(rows):
    claims=sum(r['claim_count'] for r in rows);recs=sum(r['recommendation_count'] for r in rows)
    return {'rated_outputs':len(rows),'factual_claim_count':claims,'unsupported_claim_count':sum(r['unsupported_claim_count'] for r in rows),
      'unsupported_claim_rate':fraction(sum(r['unsupported_claim_count'] for r in rows),claims),'recommendation_count':recs,
      'relevant_recommendation_rate':fraction(sum(r['relevant_recommendation_count'] for r in rows),recs),
      'read_only_recommendation_rate':fraction(sum(r['read_only_recommendation_count'] for r in rows),recs),
      'supported_recommendation_rate':fraction(sum(r['supported_recommendation_count'] for r in rows),recs),
      'mean_usefulness_1_to_5':fraction(sum(r['usefulness_1_to_5'] for r in rows),len(rows)),
      'mean_evidence_support_1_to_5':fraction(sum(r['evidence_support_1_to_5'] for r in rows),len(rows))}
