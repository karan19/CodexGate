const $ = id => document.getElementById(id);
let token = location.hash.slice(1) || sessionStorage.getItem('humanApproval');
if (location.hash) { sessionStorage.setItem('humanApproval', token); history.replaceState(null, '', '/'); }
let selected, state, busy = false;
function button(text, fn, secondary = false) { const b=document.createElement('button'); b.textContent=text; b.className=secondary?'secondary':''; b.onclick=fn; return b; }
async function request(path, body) {
  if (!token) throw Error('Open the private approval link printed in your broker Terminal.');
  const r=await fetch(path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
  const data=await r.json(); if(!r.ok) throw Error(data.error); return data;
}
function render(data) {
  state=data; $('folder').textContent=data.folder; $('session').textContent=data.session+' · '+data.scope;
  $('requests').replaceChildren();
  if(!data.requests.length) $('requests').textContent='No requests yet. Waiting for the agent.';
  for(const r of data.requests) {
    const card=document.createElement('div'); card.className='card';
    const title=document.createElement('strong'); title.textContent='Request '+r.id;
    const status=document.createElement('p'); status.className='status'; status.textContent=r.status; card.append(title,status);
    if(r.status==='pending') card.append(button('Approve for 10 minutes',()=>{selected=r.id; $('confirmation').textContent=data.session+' requests read/list access to '+data.folder+'. Request '+r.id; $('confirm').showModal();}),button('Deny',()=>act('deny',r.id),true));
    if(r.status==='authenticating') card.append(button('Deny request',()=>act('deny',r.id),true));
    if(r.status==='active') { const timer=document.createElement('p'); timer.className='countdown'; timer.textContent=Math.floor(r.remaining/60)+':'+String(r.remaining%60).padStart(2,'0')+' remaining'; card.append(timer,button('Revoke now',()=>act('revoke',r.id),true)); }
    if(['expired','revoked','denied'].includes(r.status)) {const p=document.createElement('p');p.textContent='Broker access blocked. A new request needs a new approval.';card.append(p);}
    $('requests').append(card);
  }
  $('events').replaceChildren(); for(const e of data.events) {const p=document.createElement('p');p.textContent=e.time+' · '+e.action+' · '+e.id;$('events').append(p);}
}
async function act(action,id) {try { const data=await request('/action',{action,id}); render(data); $('feedback').textContent=action==='approve'&&data.result==='denied'?'Authentication failed or cancelled. Access stays blocked.':''; }catch(e){$('feedback').textContent=e.message;} }
$('authenticate').onclick=async()=>{ if(busy)return; busy=true; $('authenticate').disabled=true; $('confirm').close(); try{await act('approve',selected);}finally{busy=false;$('authenticate').disabled=false;} };
$('cancel').onclick=()=>$('confirm').close();
async function refresh(){try{render(await request('/state'));}catch(e){$('feedback').textContent=e.message+' No access status verified.';}}
refresh(); setInterval(refresh,1000);
