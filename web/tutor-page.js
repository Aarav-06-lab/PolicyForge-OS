let jobs=[], selected='RR', busy=true, context=null;
let tutorHistory=[];
const processColor=id=>colors[Math.max(0,jobs.findIndex(p=>p.id===id))%colors.length];
function settings(){return {requirement:context.requirement,quantum:context.quantum,switch_cost:context.switch_cost};}
function saveTutorContext(){saveExperiment({...settings(),jobs,policy:selected});}
function showContext(){ $('contextSummary').textContent=`${jobs.length} jobs · Goal: ${context.requirement} · RR quantum ${context.quantum} · Switch cost ${context.switch_cost}`;$('tutorPolicy').value=selected; }
// Local tutor: retrieved lessons with fresh simulator evidence for each question.
let tutorBusy=false, tutorTopic=null;
function tutorTimeline(view){
  if(!view)return '';
  const blocks=view.trace.map(s=>`<span class="tutorslice" style="flex:${s.end-s.start};background:${s.kind==='run'?processColor(s.id):'#8a9088'}" title="${escapeHTML(s.id)}: ${s.start}–${s.end}">${escapeHTML(s.id)}<small>${s.start}–${s.end}</small></span>`).join('');
  return `<div class="tutorvisual"><b>${escapeHTML(view.label)}</b><div class="tablewrap"><div class="tutortimeline">${blocks}</div></div><p class="hint">${view.truncated?'First 100 intervals shown. Full run ends':'Run ends'} at ${view.finish} time units. Block labels show interval boundaries.</p></div>`;
}
function tutorResponse(data){
  const context=data.context?`Snapshot: ${names[data.context.policy]} · ${data.context.job_count} jobs · quantum ${data.context.quantum} · switch cost ${data.context.switch_cost}`:'Project concepts';
  return `<article class="tutoranswer"><span class="tutormeta">${escapeHTML(context)}</span><h3>${escapeHTML(data.title)}</h3>${data.generative?`<div class="generatedanswer"><span class="pill">GENERATED · ${escapeHTML(data.generative.model)}</span><p>${escapeHTML(data.generative.text)}</p><p class="hint">Generated explanation may contain errors. The numerical evidence below comes from the simulator.</p></div>`:''}${data.model_note?`<p class="tutorwarning">${escapeHTML(data.model_note)}</p>`:''}${data.paragraphs.map(p=>`<p>${escapeHTML(p)}</p>`).join('')}${data.context_note?`<p class="tutorwarning">${escapeHTML(data.context_note)}</p>`:''}${data.steps?.length?`<div class="tutorworked"><b>Worked calculation</b><ol>${data.steps.map(s=>`<li>${escapeHTML(s)}</li>`).join('')}</ol></div>`:''}${tutorTimeline(data.timeline)}${tutorTimeline(data.alternative_trace)}${data.table?`<details class="processdetails"><summary>Show the numerical evidence</summary><div class="tablewrap"><table><thead><tr>${data.table.columns.map(c=>`<th>${escapeHTML(c)}</th>`).join('')}</tr></thead><tbody>${data.table.rows.map(row=>`<tr>${row.map(c=>`<td>${escapeHTML(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div></details>`:''}${data.action?`<button type="button" class="examplebutton tutorapply" data-tutor-quantum="${Number(data.action.quantum)}">${escapeHTML(data.action.label)}</button>`:''}<div class="tutorsuggestions">${(data.suggestions||[]).map(q=>`<button type="button" data-ask="${escapeHTML(q)}">${escapeHTML(q)}</button>`).join('')}</div><details class="tutorprovenance"><summary>Answer sources & matching method</summary><p>${escapeHTML(data.method)}. ${data.matched_example?`Matched question: ${escapeHTML(data.matched_example)}. Similarity: ${fmt(data.match_score)} (not a probability).`:''}</p><p>${(data.sources||[]).map(escapeHTML).join(' · ')}</p></details></article>`;
}
async function askStudyTutor(question){
  if(tutorBusy||busy||!context||!question.trim())return;
  tutorBusy=true;$('askTutor').disabled=true;$('askTutor').textContent='Thinking…';
  $('tutorQuestion').value='';
  const questionNode=document.createElement('div');questionNode.className='tutorquestion';questionNode.textContent=question;
  $('tutorChat').appendChild(questionNode);
  const pending=document.createElement('div');pending.className='tutorpending';pending.textContent='Finding a lesson and checking your experiment…';$('tutorChat').appendChild(pending);
  $('tutor').scrollIntoView({behavior:'smooth',block:'start'});
  try{
    const data=await api('/api/tutor',{question,...settings(),jobs,policy:selected,previous_topic:tutorTopic,mode:$('tutorMode').value,history:tutorHistory});
    if(data.topic)tutorTopic=data.topic;
    tutorHistory.push({role:'user',content:question},{role:'assistant',content:(data.generative?.text||data.paragraphs.join(' ')).slice(0,1200)});tutorHistory=tutorHistory.slice(-6);
    pending.outerHTML=tutorResponse(data);
    $('tutorChat').scrollTop=$('tutorChat').scrollHeight;
  }catch(e){pending.className='tutorwarning';pending.textContent=e instanceof TypeError?'The local server is not reachable. Keep python3 -B server.py running in Terminal, then ask again.':e.message;}
  finally{tutorBusy=false;$('askTutor').disabled=false;$('askTutor').textContent='Ask tutor →';
    while($('tutorChat').children.length>17)$('tutorChat').firstElementChild.remove();}
}
$('tutorForm').addEventListener('submit',e=>{e.preventDefault();askStudyTutor($('tutorQuestion').value.trim());});
$('tutorQuestion').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();askStudyTutor($('tutorQuestion').value.trim());}});
$('tutor').addEventListener('click',e=>{
  const question=e.target.closest('[data-ask]'),apply=e.target.closest('[data-tutor-quantum]');
  if(question)askStudyTutor(question.dataset.ask);
  if(apply&&!busy&&!tutorBusy){context.quantum=Number(apply.dataset.tutorQuantum);saveTutorContext();window.location.href='/#results';}
});
$('clearTutor').onclick=()=>{if(tutorBusy)return;tutorTopic=null;tutorHistory=[];$('tutorChat').innerHTML='<div class="tutorwelcome">Chat cleared. Ask a scheduling or project-AI question using the current experiment.</div>';};


$('tutorPolicy').onchange=()=>{selected=$('tutorPolicy').value;saveTutorContext();};
async function startTutor(reset=false){
 if(reset){tutorTopic=null;tutorHistory=[];}
 busy=true;$('askTutor').disabled=true;
 try{
  context=reset?null:readExperiment();
  if(!context){const r=await fetch('/api/benchmark');if(!r.ok)throw new Error('Could not load the review example.');context={jobs:await r.json(),requirement:'interactive jobs must start within 2 units',quantum:2,switch_cost:0,policy:'RR'};}
  jobs=context.jobs;selected=names[context.policy]?context.policy:'RR';showContext();saveTutorContext();
  const r=await fetch('/api/tutor/status');if(!r.ok)throw new Error('Could not check model status.');const status=await r.json();
  $('tutorMode').value=status.configured?'generative':'local';
  $('generativeOption').disabled=!status.configured;$('generativeOption').textContent=status.configured?`Generative AI (${status.provider}: ${status.model})`:'Generative model (not configured)';
  $('modelStatus').textContent=status.configured?`${status.provider} key configured for ${status.model}. Generative AI is selected. Type your question below and press Ask tutor; the connection is checked when you ask.`:'Local tutor is active. Generative AI is not configured: set GEMINI_API_KEY or OPENAI_API_KEY on the server.';
  $('tutorPageError').hidden=true;
 }catch(e){$('tutorPageError').textContent=e.message;$('tutorPageError').hidden=false;}
 finally{busy=false;$('askTutor').disabled=!context;}
}
$('tutorMode').onchange=()=>{
 $('modelStatus').textContent=$('tutorMode').value==='generative'
  ? 'Generative AI selected. Ask a question below. Your question and evidence go to the configured provider.'
  : 'Local tutor selected. Answers use local lessons and simulator calculations.';
};
$('resetTutorContext').onclick=()=>{if(!tutorBusy)startTutor(true);};
startTutor().then(()=>{const q=new URLSearchParams(window.location.search).get('question');if(q)$('tutorQuestion').value=q.slice(0,600);});
