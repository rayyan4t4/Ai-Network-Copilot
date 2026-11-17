'use strict';
let rows=[],selected=null;const acked=new Set(),$=id=>document.getElementById(id);
function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);return n;}
async function post(path,data){return fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Copilot-Action':'review'},body:JSON.stringify(data)});}
function detail(){const d=$('detail');d.replaceChildren();const r=rows.find(x=>x.result_id===selected);if(!r){d.append(el('h2','Select a result'));return;}
 d.append(el('h2',r.approach+' · '+r.status),el('p','Case '+r.case_id),el('p','Result '+r.result_id));
 if(r.prediction)d.append(el('h3',r.prediction.fault_class+' · '+(r.prediction.device_id||'No target')+' '+(r.prediction.interface||'')));
 if(r.response){d.append(el('p',r.response.summary||r.reason||''),el('p',r.response.uncertainty||''));}
 d.append(el('p','Interpretations are tentative. Citation membership is checked automatically. Semantic support and usefulness require independent reviewers. Feedback is stored without changing models or rules.'));
 if(r.read_only_checks?.length){d.append(el('h3','Suggested read-only checks'));r.read_only_checks.forEach(x=>d.append(el('pre',x.device_id+': '+x.command)));}
 const f=el('form');f.innerHTML='<h3>Human feedback</h3><label>Reviewer name<input name="reviewer" required maxlength="100"></label><label>Decision<select name="decision"><option value="confirm">Confirm</option><option value="reject">Reject</option><option value="correct">Correct</option></select></label><label>Correction<textarea name="correction" maxlength="2000"></textarea></label><label>Usefulness <select name="usefulness"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></label><label>Evidence support <select name="supported"><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></label><label>Notes<textarea name="notes" maxlength="2000"></textarea></label><button type="submit">Save feedback</button><p id="message"></p>';
 f.addEventListener('submit',async e=>{e.preventDefault();const data=Object.fromEntries(new FormData(f));data.target_id=r.result_id;data.usefulness=Number(data.usefulness);data.supported=Number(data.supported);try{const res=await post('/api/feedback',data);$('message').textContent=res.ok?'Feedback saved. No learning or configuration changes applied.':'Feedback not saved. A reviewer name and correction for Correct are required.';}catch{$('message').textContent='Service unavailable. Feedback was not confirmed.';}});d.append(f);
 const evidence=el('details');evidence.append(el('summary','Archived model input and validation'),el('pre',JSON.stringify({request:r.request,validation:r.validation,gate:r.gate},null,2)));d.append(evidence);
}
async function refresh(){try{const res=await fetch('/api/results');if(!res.ok)throw Error();rows=(await res.json()).results;const filtered=rows.filter(r=>r.phase===$('phase').value);$('status').textContent=filtered.length+' results recorded. Display acknowledgements use this browser.';const list=$('results');list.replaceChildren();
 filtered.forEach(r=>{const b=el('button');b.className='row';b.append(el('strong',r.approach+' · '+(r.prediction?.fault_class||r.status)),el('small',r.case_id.slice(0,8)+' · '+r.status+' · '+r.available_at));b.dataset.resultId=r.result_id;b.addEventListener('click',()=>{selected=r.result_id;detail();});list.append(b);});
 const ids=filtered.filter(r=>!acked.has(r.result_id)).map(r=>r.result_id);
 if(ids.length)requestAnimationFrame(()=>requestAnimationFrame(async()=>{try{const r=await post('/api/display-ack',{result_ids:ids});if(r.ok)ids.forEach(i=>acked.add(i));}catch{}}));
 if(!selected&&filtered.length){selected=filtered[0].result_id;detail();}
 }catch{$('status').textContent='Study service disconnected. Archived results remain on disk.';}}
$('phase').addEventListener('change',()=>{selected=null;refresh();detail();});refresh();setInterval(refresh,2000);
