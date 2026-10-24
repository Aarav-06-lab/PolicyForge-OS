const explanations = {
  FCFS:'Takes ready jobs in arrival order. A long job can hold up shorter jobs behind it.',
  SJF:'Chooses the shortest job currently ready, then runs it to completion.',
  Priority:'Chooses the ready job with the smallest priority number, then runs it to completion.',
  RR:'Gives each ready job a turn of up to the time slice, then moves unfinished jobs to the back.'
};
const presets = {
  convoy:[{id:'P1',arrival:0,burst:12,priority:3,type:'batch'},{id:'P2',arrival:1,burst:2,priority:1,type:'interactive'},{id:'P3',arrival:2,burst:1,priority:2,type:'interactive'}],
  together:[{id:'P1',arrival:0,burst:7,priority:3,type:'batch'},{id:'P2',arrival:0,burst:2,priority:1,type:'interactive'},{id:'P3',arrival:0,burst:4,priority:2,type:'interactive'}]
};
let jobs=[], comparison=null, selected='RR', lastExport=null, busy=false, chartMetric='avg_response', traceIndex=0;
const processColor = id => colors[Math.max(0,jobs.findIndex(p=>p.id===id))%colors.length];
function clearSearch(){ $('breakResult').textContent=''; lastExport=null; }
function saveLabContext(){return saveExperiment({...settings(),jobs,policy:selected});}
function invalidate(){
  saveLabContext();
  comparison=null; traceIndex=0; clearSearch(); $('state').textContent='Run again to update';
  $('result').innerHTML='<div class="empty"><h3>Your inputs changed.</h3><p>Choose Compare schedulers to refresh the charts and results.</p></div>';
}
function editor(){
  $('jobs').innerHTML=jobs.map((p,i)=>`<tr><td><span class="processdot" style="background:${processColor(p.id)}"></span><input aria-label="id for process ${i+1}" data-index="${i}" data-field="id" maxlength="24" value="${escapeHTML(p.id)}"></td>${['arrival','burst','priority'].map(f=>`<td><input aria-label="${f} for process ${i+1}" data-index="${i}" data-field="${f}" type="number" min="${f==='arrival'?0:1}" max="${f==='priority'?99:1000}" value="${p[f]}"></td>`).join('')}<td><select aria-label="Type for process ${i+1}" data-index="${i}" data-field="type">${['interactive','batch','background'].map(t=>`<option ${p.type===t?'selected':''}>${t}</option>`).join('')}</select></td><td><button class="remove" aria-label="Remove process ${i+1}" data-remove="${i}">×</button></td></tr>`).join('');
  $('jobCount').textContent=`${jobs.length} ${jobs.length===1?'process':'processes'}`;
}
function settings(){return {requirement:$('requirement').value,quantum:Number($('quantum').value),switch_cost:Number($('cost').value)};}
function error(message){$('error').textContent=message;$('error').hidden=false;$('error').scrollIntoView({behavior:'smooth',block:'center'});}
function buttonState(value){
  busy=value;
  document.querySelectorAll('main input,main textarea,main select,main button').forEach(el=>el.disabled=value);
  $('compare').textContent=value?'Working…':'Compare schedulers →';
  $('compare').setAttribute('aria-busy',String(value));
}
function download(value,filename){
  const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function chart(){
  const labels={avg_response:'Time until the first turn',avg_waiting:'Total waiting time',avg_turnaround:'Time until completion'};
  const max=Math.max(1,...comparison.runs.map(r=>r[chartMetric]));
  return `<section class="chartcard"><div class="sectiontop"><div><p class="eyebrow">THE FOUR METHODS, SIDE BY SIDE</p><h3>${labels[chartMetric]}</h3></div></div><div class="charttabs" role="group" aria-label="Chart measurement">${Object.entries({avg_response:'First turn',avg_waiting:'Waiting',avg_turnaround:'Completion'}).map(([key,label])=>`<button data-metric="${key}" aria-pressed="${chartMetric===key}">${label}</button>`).join('')}</div><p class="hint">Average across all jobs · time units · shorter bars mean less time.</p><div class="bars" role="group" aria-label="Average time by scheduler">${comparison.runs.map((r,i)=>`<div class="barrow"><span>${r.policy==='RR'?'Round Robin':r.policy}</span><div class="bartrack"><div class="bar" style="width:${r[chartMetric]/max*100}%;background:${colors[i]}"></div></div><b>${fmt(r[chartMetric])}</b></div>`).join('')}</div><p class="hint">Averages can hide a slow individual job. Goal checks below use your exact requirement.</p></section>`;
}
function checkSummary(check,goal){
  if(check.status==='not_applicable')return 'There are no '+goal.group+' jobs to check. Add one or choose a goal for all jobs.';
  const metric={response:'time to first start',waiting:'waiting time',turnaround:'time to completion',max_ready_wait:'continuous time waiting for a turn'}[goal.metric];
  const subject=goal.aggregate==='average'?'Average '+metric:'Longest '+metric+' among '+(goal.group==='all'?'all':goal.group)+' jobs';
  return `${subject}: ${fmt(check.value)} units. Your goal: ${goal.operator==='<'?'less than':'at most'} ${goal.threshold} units.`;
}
function trace(run){
  traceIndex=Math.min(traceIndex,run.trace.length-1);
  const segments=run.trace.length<=180?run.trace.map((s,i)=>`<button class="slice ${i===traceIndex?'current':''}" data-slice="${i}" style="flex:${s.end-s.start};background:${s.kind==='run'?processColor(s.id):s.kind==='idle'?'#7d8784':'#9b8b7e'}" title="${escapeHTML(s.id)}: ${s.start}–${s.end}" aria-label="${escapeHTML(s.id)}, time ${s.start} to ${s.end}">${escapeHTML(s.id)}</button>`).join(''):'';
  return `<section class="tracebox"><p class="eyebrow">FOLLOW THE CPU</p><h3>${names[run.policy]}${run.policy==='RR'?` · time slice ${run.quantum}`:''}</h3><p>${explanations[run.policy]}</p><div class="goalcheck ${run.check.status}"><b>${run.check.status==='pass'?'✓ Goal met':run.check.status==='fail'?'! Goal missed':'— Goal not applicable'}</b><span>${escapeHTML(checkSummary(run.check,comparison.goal))}</span>${run.check.violations.length?`<span>${run.check.violations.map(v=>`${escapeHTML(v.id)}: ${fmt(v.value)} units`).join(' · ')}</span>`:''}</div><div class="tutorhelp"><button class="quiet" data-tutor-question="Why does ${run.policy} ${run.check.status==='pass'?'pass':'fail'} this goal?">Ask the tutor about this result ↗</button></div>${segments?`<div class="tablewrap"><div class="timeline">${segments}</div></div><div class="ticks"><span>0</span><span>${run.finish} time units</span></div><p class="hint">Each colored block is one turn. Click a block or use the step controls.</p>`:'<p class="hint">This run has many turns. Use the step controls to explore every turn.</p>'}<div class="walkthrough"><div class="walkcontrols"><button id="previous" class="examplebutton" ${traceIndex===0?'disabled':''} aria-label="Previous CPU turn">← Previous</button><span id="stepCount"></span><button id="next" class="examplebutton" ${traceIndex===run.trace.length-1?'disabled':''} aria-label="Next CPU turn">Next →</button></div><div id="turnExplanation" aria-live="polite"></div></div><details class="processdetails"><summary>All process times & calculations</summary><p>Response: time until the first turn. Waiting: total time ready but not running. Turnaround: time from arrival to completion.</p><div class="tablewrap"><table><thead><tr><th>Process</th><th>Completion</th><th>Turnaround</th><th>Waiting</th><th>Response</th><th>Longest ready wait</th></tr></thead><tbody>${run.processes.map(p=>`<tr><td>${escapeHTML(p.id)}</td><td>${p.completion}</td><td>${p.turnaround}</td><td>${p.waiting}</td><td>${p.response}</td><td>${p.max_ready_wait}</td></tr>`).join('')}</tbody></table></div><div class="metricrow"><span>CPU utilization<b>${fmt(run.utilization)}%</b></span><span>Jobs per time unit<b>${fmt(run.throughput)}</b></span><span>CPU switches<b>${run.switches}</b></span></div><p>Turnaround = completion − arrival. Waiting = turnaround − CPU time. Response = first start − arrival. Longest ready wait is the largest gap before or between turns.</p><p>Utilization and throughput cover first arrival to final completion. Switches count changes between processes, excluding the first dispatch. Switch cost reserves the selected next process during the overhead.</p></details></section>`;
}
function showTurn(){
  const run=comparison.runs.find(r=>r.policy===selected),s=run.trace[traceIndex];
  const completed=run.processes.filter(p=>p.completion<=s.start).map(p=>p.id);
  const ready=run.processes.filter(p=>p.arrival<=s.start&&p.completion>s.start&&(s.kind!=='run'||p.id!==s.id));
  $('stepCount').textContent=`Turn ${traceIndex+1} of ${run.trace.length}`;
  $('previous').disabled=traceIndex===0;$('next').disabled=traceIndex===run.trace.length-1;
  let explanation;
  if(s.kind==='idle')explanation='The CPU is idle because no job is ready yet.';
  else if(s.kind==='overhead')explanation='The CPU is spending time switching to the already selected next job.';
  else{
    const done=run.trace.slice(0,traceIndex+1).filter(t=>t.kind==='run'&&t.id===s.id).reduce((n,t)=>n+t.end-t.start,0);
    const remaining=run.processes.find(p=>p.id===s.id).burst-done;
    explanation=`${s.id} uses the CPU for ${s.end-s.start} units. ${remaining?`${remaining} CPU units remain after this turn.`:'It finishes at the end of this turn.'}`;
  }
  $('turnExplanation').innerHTML=`<b>Time ${s.start} → ${s.end}</b><p>${escapeHTML(explanation)}</p><div class="turnstatus"><span>Also ready at time ${s.start}: <strong>${ready.map(p=>escapeHTML(p.id)).join(', ')||'none'}</strong></span><span>Already finished: <strong>${completed.map(escapeHTML).join(', ')||'none'}</strong></span></div><p class="hint">Ready jobs are listed by arrival, not queue order. New arrivals during this turn appear on the next step.</p>`;
  document.querySelectorAll('[data-slice]').forEach(el=>el.classList.toggle('current',Number(el.dataset.slice)===traceIndex));
}
function advisorCard(){
  const a=comparison.advisor;
  if(!a)return '';
  if(!a.available)return `<section class="aicard"><p class="eyebrow">TRAINED AI ADVISOR</p><h3>No prediction for this goal</h3><p>${escapeHTML(a.reason)}</p></section>`;
  const label=key=>key==='NONE'?'None of the four methods':names[key];
  const e=a.evaluation;
  return `<section class="aicard"><div class="sectiontop"><div><p class="eyebrow">TRAINED AI · DECISION TREE</p><h3>AI suggests: ${label(a.prediction)}</h3></div><span class="pill">LOCAL ML MODEL</span></div><p>A learned prediction from your jobs, goal and settings. It does not calculate scheduling times.</p><div class="aiverified ${a.agrees_with_simulation?'match':'mismatch'}"><b>${a.agrees_with_simulation?'✓ Simulation agrees':'↪ Simulation corrects the prediction'}</b><span>${a.agrees_with_simulation?`The measured best choice is also ${label(a.actual_choice)}.`:`The measured best choice is ${label(a.actual_choice)}. Use the measured results below.`} ${a.prediction!=='NONE'?`The predicted method ${a.predicted_goal_status==='pass'?'does meet':'does not meet'} the goal.`:''}</span></div><div class="aistats"><span><b>${e.train_count}</b> training workloads</span><span><b>${e.correct}/${e.test_count}</b> held-out predictions correct</span><span><b>${fmt(e.accuracy*100)}%</b> test accuracy</span></div><p class="hint">Small synthetic dataset, not real OS traces. Advice can be wrong. Every recommendation is checked with the simulator.</p>${a.outside_training_ranges.length?`<p class="aicaution">Some inputs are outside training ranges: ${a.outside_training_ranges.map(escapeHTML).join(', ')}. Treat this prediction with extra caution.</p>`:''}<details class="processdetails"><summary>How this AI learned & why it chose this</summary><p><b>Training:</b> 240 generated workloads. The simulator labels each with the passing scheduler having the lowest average waiting time, or NONE if none passes. A decision tree learns feature thresholds using Gini impurity. 192 workloads train the tree; 48 separate workloads test it. Maximum depth: 5.</p><p><b>Inputs:</b> job count, burst statistics, arrival pattern, priority spread, target-job fraction, goal type and limit, quantum and switch cost. No simulator output is used as a model input.</p><p><b>This prediction followed these learned branches:</b></p><ol class="aipath">${a.path.map(p=>`<li>${escapeHTML(p.name)}: <b>${fmt(p.value)} ${escapeHTML(p.operator)} ${fmt(p.threshold)}</b></li>`).join('')||'<li>The model selected its root leaf without a split.</li>'}</ol><p>Reached a leaf containing ${a.leaf_samples} training examples. ${fmt(a.leaf_agreement*100)}% had this label. This is training-leaf agreement, not a calibrated probability of being correct.</p><p><b>Evaluation baseline:</b> always guessing “${label(e.baseline_label)}” gets ${fmt(e.baseline_accuracy*100)}% on the same test set. Model accuracy is ${fmt(e.accuracy*100)}%.</p><div class="tablewrap"><table><thead><tr><th>Label</th><th>Training examples</th><th>Test examples</th></tr></thead><tbody>${['FCFS','SJF','Priority','RR','NONE'].map(k=>`<tr><td>${label(k)}</td><td>${e.train_labels[k]||0}</td><td>${e.test_labels[k]||0}</td></tr>`).join('')}</tbody></table></div><p>Rare or absent labels limit what the model can learn. In this dataset Priority never wins the labelling rule, so this model cannot recommend it. Accuracy is an exact-label match under this rule; another passing method may still be useful.</p><p>The goal-language parser remains rule-based. The AI component is this trained classifier, not a chatbot or an LLM.</p></details></section>`;
}
function render(){
  if(!comparison)return;
  saveLabContext();
  const passing=comparison.runs.filter(r=>r.check.status==='pass').length;
  $('state').textContent='Results ready';
  $('result').innerHTML=`<div class="resultsummary"><div><span>WORKLOAD</span><b>${jobs.length} jobs</b></div><div><span>MEET YOUR GOAL</span><b>${passing} of 4 methods</b></div><div><span>RR TIME SLICE</span><b>${comparison.runs[3].quantum} units</b></div></div><p class="goal"><b>Your goal:</b> ${escapeHTML($('requirement').value)}</p><div class="notice ${passing?'':'neutral'}">${escapeHTML(comparison.recommendation.replace(/^RR /,'Round Robin '))}</div>${advisorCard()}${chart()}<div class="scorecard"><div class="tablewrap"><table><thead><tr><th>Choose a method ↓</th><th>Average waiting</th><th>Average time to start</th><th>CPU switches</th><th>Meets goal?</th></tr></thead><tbody>${comparison.runs.map(r=>`<tr data-policy="${r.policy}" class="${selected===r.policy?'selected':''}"><td><button class="quiet" data-policy="${r.policy}" aria-pressed="${selected===r.policy}">${names[r.policy]}</button></td><td>${fmt(r.avg_waiting)}</td><td>${fmt(r.avg_response)}</td><td>${r.switches}</td><td><span class="pill ${r.check.status}">${r.check.status==='not_applicable'?'N/A':r.check.status.toUpperCase()}</span></td></tr>`).join('')}</tbody></table></div><p class="hint">Choose a method to explore it below. A pass only applies to this set of jobs.</p></div>${trace(comparison.runs.find(r=>r.policy===selected))}<button id="saveComparison" class="examplebutton exportbutton">Download this experiment (JSON) ↓</button>`;
  showTurn();
  $('previous').onclick=()=>{if(traceIndex>0){traceIndex--;showTurn();}};
  $('next').onclick=()=>{if(traceIndex<comparison.runs.find(r=>r.policy===selected).trace.length-1){traceIndex++;showTurn();}};
  $('saveComparison').onclick=()=>download({configuration:settings(),jobs,...comparison},'policyforge-experiment.json');
}
async function runComparison(){
  if(busy)return; $('error').hidden=true;buttonState(true);
  try{comparison=await api('/api/compare',{...settings(),jobs});traceIndex=0;render();}
  catch(e){error(e.message);}finally{buttonState(false);if(comparison)showTurn();}
}
$('jobs').addEventListener('input',e=>{const {index,field}=e.target.dataset;if(field){jobs[index][field]=['id','type'].includes(field)?e.target.value:Number(e.target.value);invalidate();}});
$('jobs').addEventListener('click',e=>{if(busy)return;if(e.target.dataset.remove!==undefined){jobs.splice(Number(e.target.dataset.remove),1);editor();invalidate();}});
$('add').onclick=()=>{if(jobs.length>=60)return error('Maximum 60 processes.');let n=1;while(jobs.some(p=>p.id===`P${n}`))n++;jobs.push({id:`P${n}`,arrival:0,burst:3,priority:1,type:'interactive'});editor();invalidate();};
$('compare').onclick=runComparison;
$('result').addEventListener('click',e=>{
  if(busy||!comparison)return;
  const help=e.target.closest('[data-tutor-question]');if(help){saveLabContext();window.location.href='/tutor?question='+encodeURIComponent(help.dataset.tutorQuestion);return;}
  const policy=e.target.closest('[data-policy]'),metric=e.target.closest('[data-metric]'),slice=e.target.closest('[data-slice]');
  if(policy){selected=policy.dataset.policy;traceIndex=0;render();}
  if(metric){chartMetric=metric.dataset.metric;render();}
  if(slice){traceIndex=Number(slice.dataset.slice);showTurn();}
});
$('guideToggle').onclick=()=>{$('guide').hidden=!$('guide').hidden;$('guideToggle').setAttribute('aria-expanded',String(!$('guide').hidden));if(!$('guide').hidden)$('guide').scrollIntoView({behavior:'smooth',block:'start'});};
document.querySelectorAll('[data-goal]').forEach(b=>b.onclick=()=>{$('requirement').value=b.dataset.goal;invalidate();});
['requirement','quantum','cost'].forEach(id=>$(id).addEventListener('input',invalidate));
['policy','seed','budget'].forEach(id=>$(id).addEventListener('input',clearSearch));
async function loadExample(kind='review'){
  if(busy)return;buttonState(true);$('error').hidden=true;
  try{
    if(kind==='review'){const response=await fetch('/api/benchmark');if(!response.ok)throw new Error('Could not load example.');jobs=await response.json();}
    else jobs=presets[kind].map(p=>({...p}));
    $('requirement').value='interactive jobs must start within 2 units';$('quantum').value=2;$('cost').value=0;selected='RR';traceIndex=0;
    $('exampleNote').textContent={review:'Review example: one long job, followed by three shorter jobs.',convoy:'Long job first: watch how a large job delays short interactive jobs.',together:'Arrive together: compare which job each method chooses first.'}[kind];
    editor();invalidate();
  }catch(e){error(e.message);}finally{buttonState(false);}
  if(jobs.length)await runComparison();
}
$('demo').onclick=()=>loadExample();
document.querySelectorAll('[data-example]').forEach(b=>b.onclick=()=>loadExample(b.dataset.example));
$('break').onclick=async()=>{
  if(busy)return;clearSearch();$('error').hidden=true;buttonState(true);$('breakResult').textContent='Trying different sets of jobs…';
  const config={...settings(),policy:$('policy').value,seed:Number($('seed').value),budget:Number($('budget').value)};
  try{
    const data=await api('/api/break',config);
    if(!data.found){$('breakResult').innerHTML=`<div class="breakfinding"><h3>No failure found in ${data.attempts} tests.</h3><p>${escapeHTML(data.explanation)}</p></div>`;return;}
    lastExport={configuration:config,...data};
    $('breakResult').innerHTML=`<div class="breakfinding"><span class="pill fail">COUNTEREXAMPLE FOUND</span><h3>${data.jobs.length} jobs are enough to miss your goal.</h3><p>${escapeHTML(checkSummary(data.check,data.comparison.goal))} ${data.check.violations.map(v=>`${escapeHTML(v.id)} = ${fmt(v.value)}`).join('; ')}.</p><div class="searchjourney"><span><b>${data.attempts}</b> workloads tried</span><span><b>${data.original_count} → ${data.jobs.length}</b> jobs after reduction</span><span><b>${data.seed}</b> repeatable seed</span></div><p class="hint">The search removed jobs while keeping the failure. No single remaining job can be removed without losing it; this is not a globally smallest example.</p><div class="tablewrap"><table><thead><tr><th>ID</th><th>Arrives at</th><th>CPU time</th><th>Priority</th><th>Job type</th></tr></thead><tbody>${data.jobs.map(p=>`<tr><td>${escapeHTML(p.id)}</td><td>${p.arrival}</td><td>${p.burst}</td><td>${p.priority}</td><td>${escapeHTML(p.type)}</td></tr>`).join('')}</tbody></table></div><div class="actionrow"><button id="replay" class="examplebutton">Load this example & compare →</button><button id="export" class="quiet">Download results (JSON) ↓</button></div></div>`;
    $('replay').onclick=()=>{jobs=data.jobs.map(p=>({...p}));$('requirement').value=config.requirement;$('quantum').value=config.quantum;$('cost').value=config.switch_cost;comparison=data.comparison;selected=config.policy;traceIndex=0;$('exampleNote').textContent='Counterexample loaded from the failure search.';editor();render();$('result').scrollIntoView({behavior:'smooth',block:'start'});};
    $('export').onclick=()=>download(lastExport,`policyforge-seed-${config.seed}.json`);
  }catch(e){$('breakResult').textContent='';error(e.message);}finally{buttonState(false);if(comparison)showTurn();}
};
$('challengeLink').onclick=()=>{$('challenge').open=true;};


window.addEventListener('pagehide',saveLabContext);
async function startLab(){
 const saved=readExperiment();
 if(!saved){await loadExample();return;}
 jobs=saved.jobs;selected=names[saved.policy]?saved.policy:'RR';
 $('requirement').value=saved.requirement;$('quantum').value=saved.quantum;$('cost').value=saved.switch_cost;
 $('exampleNote').textContent='Your experiment restored from this browser tab.';editor();await runComparison();
}
startLab();
