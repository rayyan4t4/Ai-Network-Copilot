"""Record the secondary scoring plan before supplied reviewer ratings exist."""
import csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scripts')]
from run_study import save,now
target=ROOT/'research/human-analysis-plan-lock.json'
if target.exists():print('Human analysis plan already recorded.');raise SystemExit(0)
blank=True;rows=0
for n in (1,2):
    with (ROOT/f'docs/review/Reviewer {n}.csv').open(newline='',encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            rows+=1;blank &= not any(str(v or '').strip() for k,v in row.items() if k!='review_id')
if not blank:raise RuntimeError('Reviewer judgments already supplied; do not claim a pre-annotation lock')
files=['evaluation/human_metrics.py','scripts/analyze_human_reviews.py','docs/human-review.md','docs/review/Review instructions.md']
save(target,{'recorded_at':now(),'reviewer_fields_blank':True,'blank_rows':rows,'scope':'Secondary human-quality computations declared before supplied judgments. Primary frozen experiment unchanged.','sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}})
print('Recorded human analysis plan before ratings:',rows,'blank rows')
