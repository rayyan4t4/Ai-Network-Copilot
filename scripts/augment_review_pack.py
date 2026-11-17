"""Attach actual delivered inputs and blinded local source references for humans."""
import hashlib,html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'docs/review'
mapping=json.loads((ROOT/'.local/evaluation/control/review-blinding-map.json').read_text())
pages=['<!doctype html><meta charset="utf-8"><title>Independent diagnosis review</title><style>body{font:16px Arial;max-width:1000px;margin:40px auto;line-height:1.5}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f6;padding:18px}article{page-break-after:always;border-top:1px solid #bbb;padding-top:20px}</style><h1>Independent diagnosis review</h1><p>Rate independently using your separate CSV. First inspect the actual diagnostic input. A claim must be supported by the evidence actually supplied to that approach. Local source observations verify derived facts and are not extra model context. Approach identities are withheld, although input format differences may reveal conditions. No completed human ratings are supplied.</p>']
for ident,item in mapping.items():
    case=ROOT/'research/final'/item['case_id'];record=json.loads((case/(item['approach']+'.json')).read_text())
    pseudonym='source-'+hashlib.sha256(item['case_id'].encode()).hexdigest()[:20]+'.json'
    source=out/pseudonym
    if not source.exists():source.write_bytes((case/'observations.json').read_bytes())
    p=out/(ident+'.json');view=json.loads(p.read_text())
    view['actual_diagnostic_input']=record.get('request',{'gate':record.get('gate'),'meaning':'No model was called. Assess only the displayed deterministic result and its available observations.'})
    view['local_source_observations']=pseudonym
    view['review_boundary']='Support is relative to the actual diagnostic input. The masked source bundle is available only to verify derived observations; it must not give credit for information absent from the diagnostic input.'
    p.write_text(json.dumps(view,indent=2))
    pages.append('<article><h2>'+ident+'</h2><p><a href="'+pseudonym+'">Local source observations</a></p><pre>'+html.escape(json.dumps(view,indent=2))+'</pre></article>')
(out/'Review pack.html').write_text('\n'.join(pages),encoding='utf-8')
with (out/'Review instructions.md').open('a') as f:f.write('\n\nThe pack also includes the actual delivered diagnostic input and a blinded local source bundle. Judge support against the input actually supplied to the approach. Use source records to verify derived facts, not to credit an explanation for unsupplied information. The original unmasked capture is intentionally excluded for insufficient cases. Preserve completed reviewer sheets before regenerating the pack.\n')
print('Augmented',len(mapping),'blinded outputs with delivered inputs and local source references.')
