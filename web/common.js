'use strict';
const $ = id => document.getElementById(id);
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = x => x == null ? '—' : Number(x).toFixed(2).replace(/\.00$/, '');
const colors = ['#386d85','#bd613d','#65854b','#9370a5','#bd8b33','#37877c','#a85d75','#647eac'];
const names = {FCFS:'First come, first served', SJF:'Shortest job first', Priority:'Priority', RR:'Round Robin'};
async function api(path,data){
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result=await response.json(); if(!response.ok)throw new Error(result.error||'The experiment could not run.'); return result;
}

const EXPERIMENT_KEY='policyforge-experiment-v1';
function readExperiment(){try{const s=JSON.parse(sessionStorage.getItem(EXPERIMENT_KEY));return s&&Array.isArray(s.jobs)&&s.jobs.length>0&&s.jobs.length<=60&&s.jobs.every(p=>p&&typeof p.id==='string'&&Number.isInteger(p.arrival)&&Number.isInteger(p.burst))&&typeof s.requirement==='string'&&Number.isInteger(s.quantum)&&Number.isInteger(s.switch_cost)?s:null;}catch{return null;}}
function saveExperiment(value){try{sessionStorage.setItem(EXPERIMENT_KEY,JSON.stringify(value));return true;}catch{return false;}}
