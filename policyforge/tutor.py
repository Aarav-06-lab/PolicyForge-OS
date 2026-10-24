"""Local study tutor: TF-IDF question retrieval plus verified simulator examples.

This is retrieval-based AI, not an LLM. It does not generate arbitrary factual text.
The corpus contains authored lessons and question examples. The numerical evidence
comes from the simulator, not from a language model.
"""
from collections import Counter
from functools import lru_cache
from math import log, sqrt
import re
from .core import simulate, validate, POLICIES
from .experiments import parse_goal, verify, BENCHMARK
from .advisor import advise

# Example questions form a small local retrieval corpus. No user chats train the model.
LESSONS = {
 'round_robin': ('How Round Robin shares the CPU',
  ['what is round robin', 'explain rr scheduling', 'how round robin ready queue works', 'why does unfinished process go back', 'how does rr choose the next process'],
  ['Round Robin takes the process at the front of the ready queue and gives it up to one quantum of CPU time. If unfinished, it goes to the back. If finished, it leaves the queue.',
   'New arrivals join the ready queue. In this simulator, arrivals exactly at a turn endpoint enter before the interrupted process returns to the back.']),
 'quantum': ('Time slice and switching trade-offs',
  ['what is quantum time slice', 'what happens if i change quantum to 1', 'does smaller quantum make round robin faster', 'show quantum comparison', 'what if time slice is 4', 'why more cpu switches with small quantum'],
  ['The quantum is the maximum length of a Round Robin turn. A job needing less time finishes early. Smaller turns can reduce first-response delay but can create more process switches.',
   'With a quantum at least as large as every burst, Round Robin behaves like FCFS under the same queue rules. A shorter quantum does not guarantee every goal will pass.']),
 'failure': ('Why this scheduler passes or fails',
  ['why does my scheduler fail', 'why did p4 fail the goal', 'explain this result', 'why does it say pass', 'all processes finish so why failed', 'which job violates the requirement'],
  ['PASS means the measured result satisfies the selected goal. FAIL means at least one required condition is violated. All jobs can finish successfully while a response-time goal fails.',
   'For an individual response goal, every targeted job must start within the limit measured from its own arrival. An average can hide one slow job.']),
 'response': ('Response time: delay until the first turn',
  ['what is response time', 'how calculate p2 response', 'when does p4 first start', 'first start minus arrival', 'why average response is two'],
  ['Response time = first CPU start − arrival. It counts only the wait before a job first executes, not time until completion.',
   'Average response adds all process response times and divides by the number of processes. Your goal may instead check each targeted process individually.']),
 'waiting': ('Waiting time: all time ready but not running',
  ['what is waiting time', 'calculate p2 waiting', 'why does p1 wait seven', 'how much time spent waiting', 'difference waiting and response time'],
  ['Waiting time = completion − arrival − CPU burst. It includes the initial delay and waits between later turns.',
   'Response counts only the initial wait. Turnaround includes waiting and CPU execution in this one-burst simulation.']),
 'turnaround': ('Turnaround and completion',
  ['what is turnaround time', 'calculate p2 turnaround', 'difference completion and turnaround', 'when does p4 finish', 'completion time calculation'],
  ['Turnaround time = completion − arrival. Completion is a clock time; turnaround is a duration.',
   'For example, arrival at 1 and completion at 11 gives turnaround 10. Subtract its CPU burst to find total waiting time.']),
 'job_type': ('Job type selects which jobs the goal checks',
  ['what is job type', 'difference interactive batch background', 'what if p4 becomes background', 'change p1 type to batch', 'does type change execution order', 'why changing type changes pass fail'],
  ['Interactive represents work needing quick interaction, batch represents bulk processing, and background represents maintenance. These are simplified labels in this project.',
   'Type does not change any scheduling order here. It changes which jobs a goal checks. Relabelling a slow interactive job as background does not make it faster. Goals for all jobs still check every type.']),
 'fcfs': ('First come, first served',
  ['what is fcfs', 'explain first come first served', 'what is convoy effect', 'long job blocking short jobs', 'fcfs selection rule'],
  ['FCFS runs ready jobs in arrival order and lets the selected job finish. A long job can hold up shorter jobs behind it, called the convoy effect.',
   'For equal arrivals, this simulator uses process ID to break the tie. FCFS does not use priority or job type to choose.']),
 'sjf': ('Shortest job first',
  ['what is sjf', 'explain shortest job first', 'why shortest available job executes', 'is sjf preemptive', 'why sjf does not interrupt p1'],
  ['SJF chooses the ready job with the smallest known CPU burst. Our implementation is non-preemptive: a later short job cannot interrupt one already running.',
   'Known burst lengths are a simulation assumption. An operating system does not generally know exact future execution times.']),
 'priority': ('Priority scheduling',
  ['what is priority scheduling', 'does high number mean high priority', 'why priority 1 first', 'how priority scheduler works', 'does priority affect round robin'],
  ['Our Priority scheduler selects the ready job with the smallest priority number and runs it to completion. Arrival and ID break ties.',
   'Only this policy uses the priority field for selection. It does not change Round Robin, FCFS or SJF.']),
 'inputs': ('Processes, arrival and CPU bursts',
  ['what is a process workload', 'what is burst cpu time', 'what does arrival mean', 'explain setup inputs', 'are time units seconds'],
  ['A workload is the collection of jobs. Each job has an ID, arrival, CPU burst, priority and type. Arrival says when it becomes ready; burst says how much CPU execution it needs.',
   'Time units are simulated ticks, not seconds measured on your Mac. The project models one CPU and one known burst per process, with no I/O blocking.']),
 'switch': ('Context-switch overhead',
  ['what is switch cost', 'what is context switching overhead', 'why cpu utilization goes down', 'what are cpu switches', 'why rr has eleven switches'],
  ['A process switch occurs when successive execution turns belong to different jobs. Initial dispatch is excluded; consecutive turns of the same job do not add a switch.',
   'Switch cost advances the simulated clock without doing useful job execution. The selected next job stays reserved during that overhead.']),
 'utilization': ('CPU utilization and throughput',
  ['what is cpu utilization', 'what does throughput mean', 'how calculate utilization percentage', 'why utilization is 100 percent', 'jobs per time unit'],
  ['Utilization = useful CPU execution / elapsed time × 100. Throughput = completed jobs / elapsed time.',
   'This project measures elapsed time from the first arrival to the last completion. Initial idle time before the first arrival is excluded.']),
 'tree': ('The trained AI decision tree',
  ['how does ai decision tree predict', 'what ai model is used', 'is this chatgpt api', 'what are features', 'what is advisor py', 'why ai prediction wrong', 'what does ai fetch'],
  ['The scheduler advisor is a supervised decision tree implemented locally in Python. It reads advisor_model.json and follows learned feature thresholds to a predicted scheduler label or NONE.',
   'It uses 17 input features, including burst statistics, arrivals, goal and quantum. It does not receive measured scheduler outputs as features. The simulator independently checks its prediction.']),
 'training': ('How the scheduler model learns',
  ['how was ai trained', 'where are 240 training examples', 'what is train advisor py', 'dataset versus model file', 'how labels generated', 'what is supervised learning'],
  ['scripts/train_advisor.py generates 240 distinct synthetic workloads. The simulator supplies a label: the passing method with least average waiting, then fewer switches; NONE if none passes.',
   'It splits 192 workloads for fitting and 48 for testing before learning. fit() learns the tree and the script saves advisor_dataset.json and advisor_model.json. Website clicks use the saved model, not retraining.']),
 'gini': ('Gini impurity chooses useful questions',
  ['what is gini impurity', 'how does fit select splits', 'why tree asks these questions', 'what is weighted gini', 'how decision tree learns thresholds'],
  ['Gini impurity measures label mixing: 1 − sum of squared class proportions. A group with only RR labels has Gini 0. Half RR and half SJF gives 1 − 0.5² − 0.5² = 0.5.',
   'fit() tries numeric cutoffs and prefers a split with lower size-weighted impurity. It repeats recursively up to depth 5, with at least 5 examples per leaf.']),
 'accuracy': ('Accuracy and model limitations',
  ['what is model accuracy', 'why 66 percent', 'what is baseline', 'what is overfitting', 'why ai never predicts priority', 'explain test set confusion matrix'],
  ['The advisor gets 32 of 48 held-out labels right: 66.7%. Always guessing the most common training label, NONE, gets 27 of 48: 56.3%. This is one small synthetic evaluation.',
   'No training workload labels Priority as the winner, so the model cannot predict it. Depth and leaf-size limits help limit overfitting. Leaf agreement is not calibrated confidence.']),
 'search': ('Finding and reducing a counterexample',
  ['how break my scheduler works', 'what is seed budget counterexample', 'how failure search reduces jobs', 'does no failure prove correct', 'is randomized search ai'],
  ['The search generates workloads, runs your selected scheduler and stops at the first goal failure or budget limit. A fixed seed repeats the same random sequence.',
   'It removes one process at a time while preserving the failure. This is deletion-minimal, not a globally smallest workload. The search is randomized testing, separate from the trained classifier.']),
 'architecture': ('How the website and Python code connect',
  ['explain project architecture', 'what happens when compare clicked', 'which file does simulation', 'how frontend backend communicate', 'what is core py server py'],
  ['web/app.js sends JSON to server.py. experiments.py parses the goal, runs comparisons and checks requirements. core.py simulates each scheduler; advisor.py predicts from the saved model.',
   'Python returns JSON with timings, traces, checks and AI advice. JavaScript draws the charts and timeline. The local server must remain running.']),
 'tutor': ('How this local tutor works',
  ['how does tutor answer questions', 'is tutor an llm', 'how tutor trained', 'what is tf idf cosine similarity', 'can you answer anything', 'what can i ask'],
  ['This tutor uses TF-IDF vectors and cosine similarity to retrieve a matching authored lesson from example questions. It then runs the simulator to show current-workload evidence.',
   'It is retrieval-based AI, not a generative LLM or internet search. It covers scheduling and this project’s AI. If it cannot match a question reliably, it asks you to rephrase instead of inventing an answer.']),
 'recommendation': ('Choosing a scheduler for this goal',
  ['which scheduler is best', 'what should i choose', 'recommend a scheduler', 'why no method meets goal', 'can you suggest best algorithm'],
  ['There is no universally best scheduler. This lab first requires a goal pass, then chooses the lowest average waiting time, then fewer switches. Remaining ties follow FCFS, SJF, Priority, RR order.',
   'A learned prediction can be wrong. Use the measured simulator result for this workload and configuration.'])
}
STOP = set('a an the is are was were what how why does do did i my me you your it its this that to of for and or in on with can please tell explain about show basic mean means'.split())

def tokens(text):
    text = re.sub(r'\bp\d+\b', 'process', text.lower())
    text = text.replace('round-robin','round robin').replace('time-slice','time slice')
    return [t for t in re.findall(r'[a-z][a-z_]+',text) if t not in STOP]

@lru_cache(maxsize=1)
def retrieval_model():
    docs=[(topic,q) for topic,(_,questions,_) in LESSONS.items() for q in questions]
    counts=[Counter(tokens(q)) for _,q in docs]
    df=Counter(t for doc in counts for t in doc)
    idf={t:log((1+len(docs))/(1+n))+1 for t,n in df.items()}
    def vector(count):
        v={t:(1+log(n))*idf[t] for t,n in count.items() if t in idf}
        norm=sqrt(sum(n*n for n in v.values())) or 1
        return {t:n/norm for t,n in v.items()}
    return docs,idf,[vector(c) for c in counts]

def retrieve(question, previous_topic=None):
    docs,idf,vectors=retrieval_model();counts=Counter(tokens(question))
    v={t:(1+log(n))*idf[t] for t,n in counts.items() if t in idf}
    norm=sqrt(sum(n*n for n in v.values())) or 1
    v={t:n/norm for t,n in v.items()}
    matches=sorted([(sum(weight*vector.get(t,0) for t,weight in v.items()),topic,q)
                    for (topic,q),vector in zip(docs,vectors)],reverse=True)
    # Short follow-ups stay on the last known topic. Ignore unknown topic identifiers.
    if previous_topic in LESSONS and question.lower().strip(' ?!.') in ('why','show an example','show me an example','explain more','tell me more','show the calculation','how about this example'):
        return previous_topic,1.0,'Follow-up to previous topic'
    score,topic,matched=matches[0]
    return (topic if score>=0.28 and v else None),score,matched


def answer(question, jobs=None, requirement='interactive jobs must start within 2 units',
           quantum=2, switch_cost=0, policy='RR', previous_topic=None):
    if not isinstance(question,str) or not question.strip() or len(question)>600:
        raise ValueError('Ask a question of 1–600 characters.')
    if policy not in POLICIES:raise ValueError('Choose a supported scheduler for the tutor.')
    topic,score,matched=retrieve(question,previous_topic)
    response={'topic':topic,'match_score':round(score,3),'method':'TF-IDF question retrieval + deterministic simulation',
              'suggestions':['Why does this scheduler fail?', 'Calculate P2 waiting time', 'What if quantum is 1?', 'How was the AI trained?']}
    if not topic:
        return {**response,'title':'Let’s keep this within the scheduling lab',
                'paragraphs':['I could not match that question reliably. Ask about a scheduling algorithm, a process calculation, quantum, job types, failure search, or the project’s AI. I do not generate general-purpose answers.'],
                'supported':False}
    title,_,paragraphs=LESSONS[topic]
    response.update(title=title,paragraphs=list(paragraphs),supported=True,matched_example=matched)
    jobs=BENCHMARK if jobs is None else jobs
    # Concepts remain available while a user has temporarily invalid experiment inputs.
    try:
        validate(jobs)
        mentioned={'rr':'RR','round robin':'RR','fcfs':'FCFS','first come first served':'FCFS',
                   'sjf':'SJF','shortest job first':'SJF','priority':'Priority'}
        for phrase,choice in mentioned.items():
            if re.search(r'\b'+re.escape(phrase)+r'\b',question.lower()):policy=choice
        if topic in ('fcfs','sjf','priority','round_robin'):
            policy={'fcfs':'FCFS','sjf':'SJF','priority':'Priority','round_robin':'RR'}[topic]
        run=simulate(jobs,policy,quantum,switch_cost)
    except (ValueError,TypeError,KeyError) as exc:
        response['context_note']='I can explain the concept, but cannot calculate this experiment until its inputs are fixed: '+str(exc)
        return response
    response['context']={'policy':policy,'quantum':quantum,'switch_cost':switch_cost,'job_count':len(jobs)}
    goal=None
    try:goal=parse_goal(requirement)
    except ValueError:response['context_note']='Your goal wording is unsupported. Timing examples still use the current jobs and settings.'
    pid=next((p['id'] for p in jobs if re.search(r'(?<!\w)'+re.escape(p['id'])+r'(?!\w)',question,re.I)),None)
    requested=re.search(r'\bp\d+\b',question,re.I)
    if requested and not pid:
        response['context_note']=f"There is no {requested.group(0)} in your current workload. Ask about one of: "+', '.join(p['id'] for p in jobs)
        return response
    row=next((p for p in run['processes'] if p['id']==pid),None)
    if row is None:row=next((p for p in run['processes'] if p['id']=='P2'),run['processes'][0])
    def evidence_table(columns,rows):return {'columns':columns,'rows':rows}
    if topic in ('response','waiting','turnaround','inputs') or (pid and topic not in ('quantum','job_type','failure')):
        first=row['arrival']+row['response']
        response['steps']=[f"{row['id']}: arrives at {row['arrival']}, needs {row['burst']} CPU units, first runs at {first}, finishes at {row['completion']}.",
            f"Response = {first} − {row['arrival']} = {row['response']}.",
            f"Turnaround = {row['completion']} − {row['arrival']} = {row['turnaround']}.",
            f"Waiting = {row['turnaround']} − {row['burst']} = {row['waiting']}."]
    if topic in ('failure','job_type','recommendation'):
        if goal:
            check=verify(run,goal)
            response['paragraphs'].append(f"Current {policy} result: {check['status'].replace('_',' ')}. {check['explanation']}")
            if check['violations']:
                response['steps']=[f"{v['id']}: measured {v['value']:g} units; goal requires {goal['operator']} {goal['threshold']}." for v in check['violations']]
            if topic=='job_type':
                kind=re.search(r'\b(interactive|batch|background)\b',question.lower())
                if pid and kind:
                    changed=[dict(p,type=kind.group(1)) if p['id']==pid else dict(p) for p in jobs]
                    alternative=simulate(changed,policy,quantum,switch_cost);other=verify(alternative,goal)
                    response['paragraphs'].append(f"If {pid} becomes {kind.group(1)}, the same timeline yields goal status {other['status'].replace('_',' ')}. Its execution timing does not change.")
            if topic=='recommendation':
                runs=[simulate(jobs,k,quantum,switch_cost) for k in POLICIES]
                passing=[r for r in runs if verify(r,goal)['status']=='pass']
                best=min(passing,key=lambda r:(r['avg_waiting'],r['switches'])) if passing else None
                response['paragraphs'].append(f"Measured choice for these inputs: {best['policy'] if best else 'no goal-passing method'}. This is a simulated result, not an AI guess.")
                response['table']=evidence_table(['Method','Average waiting','Goal'],[[r['policy'],round(r['avg_waiting'],2),verify(r,goal)['status']] for r in runs])
    if topic=='quantum':
        match=re.search(r'(?:quantum|time slice|slice|\bq)\s*(?:is|to|of|=)?\s*(\d+)',question.lower())
        alternative_q=int(match.group(1)) if match else (1 if quantum!=1 else 2)
        if not 1<=alternative_q<=100:
            response['paragraphs'].append('The supported quantum range is 1–100.');return response
        current=simulate(jobs,'RR',quantum,switch_cost);alternate=simulate(jobs,'RR',alternative_q,switch_cost)
        response['table']=evidence_table(['RR quantum','Avg response','Avg waiting','Switches','Goal'],
            [[q,round(r['avg_response'],2),round(r['avg_waiting'],2),r['switches'],verify(r,goal)['status'] if goal else 'unsupported goal'] for q,r in [(quantum,current),(alternative_q,alternate)]])
        response['paragraphs'].append(f"This compares your current quantum {quantum} with {alternative_q} on exactly the same jobs and switch cost {switch_cost}.")
        response['alternative_trace']={'label':f'Round Robin, quantum {alternative_q}','trace':alternate['trace'][:100],'finish':alternate['finish'],'truncated':len(alternate['trace'])>100}
        response['action']={'label':f'Try quantum {alternative_q} in the main experiment','quantum':alternative_q}
        run=current;response['context']['policy']='RR'
    if topic=='utilization':
        elapsed=run['finish']-min(p['arrival'] for p in jobs);total=sum(p['burst'] for p in jobs)
        response['steps']=[f"Useful CPU time = {total}. Elapsed time from first arrival = {elapsed}.",f"Utilization = {total} / {elapsed} × 100 = {run['utilization']:.2f}%.",f"Throughput = {len(jobs)} / {elapsed} = {run['throughput']:.3f} jobs per unit."]
    if topic in ('tree','accuracy') and goal:
        a=advise(jobs,goal,quantum,switch_cost)
        if a['available']:
            response['paragraphs'].append(f"For your inputs, the saved advisor predicts {a['prediction']}. It follows {len(a['path'])} learned branches.")
            response['table']=evidence_table(['Learned feature','Your value','Branch'],[[p['name'],round(p['value'],3),f"{p['operator']} {p['threshold']:.3g}"] for p in a['path']])
    if topic in ('round_robin','fcfs','sjf','priority','response','waiting','turnaround','failure','quantum','job_type','switch'):
        response['timeline']={'label':f"{run['policy']} timeline"+ (f", quantum {run['quantum']}" if run['policy']=='RR' else ''),'trace':run['trace'][:100],'finish':run['finish'],'truncated':len(run['trace'])>100}
        if 'table' not in response:
            response['table']=evidence_table(['Job','Arrival','Burst','First start','Finish','Response','Waiting'],[[p['id'],p['arrival'],p['burst'],p['arrival']+p['response'],p['completion'],p['response'],p['waiting']] for p in run['processes']])
    response['sources']=['Local authored lesson: '+topic,'Simulator: policyforge/core.py' if topic not in ('training','gini','accuracy','tree','architecture','tutor') else 'Project implementation and saved model']
    return response
