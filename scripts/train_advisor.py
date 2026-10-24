"""Rebuild the student-scale advisor: python3 -B scripts/train_advisor.py."""
import json
from collections import Counter
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from policyforge.advisor import features, fit, predict, FEATURE_LABELS
from policyforge.experiments import compare

ROOT=Path(__file__).resolve().parents[1]

def make_dataset(seed=1707, count=240):
    rng=random.Random(seed);rows=[]
    for index in range(count):
        simultaneous=rng.choice([True,False])
        jobs=[{'id':f'P{i+1}','arrival':0 if simultaneous else rng.randint(0,10),
               'burst':rng.randint(1,20),'priority':rng.randint(1,5),
               'type':rng.choice(['interactive','batch','background'])}
              for i in range(rng.randint(3,10))]
        metric=rng.choice(['response','waiting','turnaround','max_ready_wait'])
        aggregate='each' if metric=='max_ready_wait' else rng.choice(['each','average']) if metric=='response' else 'average'
        group=rng.choice(['all','interactive','batch','background']) if aggregate=='each' else 'all'
        if group!='all': jobs[0]['type']=group
        goal={'metric':metric,'aggregate':aggregate,'group':group,
              'operator':rng.choice(['<','<=']) if aggregate=='average' else '<=',
              'threshold':rng.randint(1,10) if metric=='response' else rng.randint(3,35)}
        quantum=rng.choice([1,2,3,4]);cost=rng.choice([0,0,0,1])
        result=compare(jobs,goal,quantum,cost,include_advisor=False)
        passing=[r for r in result['runs'] if r['check']['status']=='pass']
        best=min(passing,key=lambda r:(r['avg_waiting'],r['switches'])) if passing else None
        rows.append({'id':index,'jobs':jobs,'goal':goal,'quantum':quantum,'switch_cost':cost,
                     'features':features(jobs,goal,quantum,cost),'label':best['policy'] if best else 'NONE'})
    return rows

def train():
    rows=make_dataset()
    # Split whole workloads before fitting; the held-out set never chooses splits or depth.
    order=list(range(len(rows)));random.Random(909).shuffle(order)
    test_ids=set(order[:48]);train=[r for r in rows if r['id'] not in test_ids];test=[r for r in rows if r['id'] in test_ids]
    tree=fit(train)
    baseline=Counter(r['label'] for r in train).most_common(1)[0][0]
    labels=['FCFS','SJF','Priority','RR','NONE']
    confusion={a:{b:0 for b in labels} for a in labels}
    for row in test:
        guess=predict(tree,row['features'])[0]['prediction'];confusion[row['label']][guess]+=1
    evaluation={'train_count':len(train),'test_count':len(test),
                'correct':sum(confusion[k][k] for k in labels),
                'accuracy':sum(confusion[k][k] for k in labels)/len(test),
                'baseline_label':baseline,'baseline_accuracy':sum(r['label']==baseline for r in test)/len(test),
                'train_labels':dict(Counter(r['label'] for r in train)),
                'test_labels':dict(Counter(r['label'] for r in test)), 'confusion_matrix':confusion}
    model={'version':1,'dataset_seed':1707,'split_seed':909,'max_depth':5,'min_leaf':5,
           'label_rule':'Among goal-passing schedulers, minimum average waiting then minimum switches; ties follow FCFS, SJF, Priority, RR order. NONE means none passes.',
           'features':FEATURE_LABELS,'feature_ranges':{k:[min(r['features'][k] for r in train),max(r['features'][k] for r in train)] for k in FEATURE_LABELS},
           'evaluation':evaluation,'tree':tree}
    for row in rows:row['split']='test' if row['id'] in test_ids else 'train'
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data'/'advisor_dataset.json').write_text(json.dumps(rows,indent=2)+'\n')
    (ROOT/'data'/'advisor_model.json').write_text(json.dumps(model,indent=2)+'\n')
    print(json.dumps(evaluation,indent=2))
if __name__=='__main__':train()
