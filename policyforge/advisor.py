"""A small supervised decision tree. Inference uses inputs, never simulator results."""
from collections import Counter
from functools import lru_cache
from math import sqrt
from pathlib import Path
import json

MODEL_PATH = Path(__file__).resolve().parent.parent / 'data' / 'advisor_model.json'
FEATURE_LABELS = {
    'job_count': 'number of jobs', 'mean_burst': 'average CPU burst',
    'max_burst': 'longest CPU burst', 'burst_spread': 'variation in CPU bursts',
    'arrival_spread': 'arrival time spread', 'initial_jobs': 'jobs at first arrival',
    'target_fraction': 'fraction of jobs checked by the goal',
    'priority_spread': 'priority spread', 'quantum': 'Round Robin time slice',
    'switch_cost': 'switch cost', 'threshold': 'goal limit',
    'metric_response': 'goal measures first response (1=yes)',
    'metric_waiting': 'goal measures waiting (1=yes)',
    'metric_turnaround': 'goal measures turnaround (1=yes)',
    'metric_ready_wait': 'goal measures continuous ready wait (1=yes)',
    'average_goal': 'goal checks an average (1=yes)', 'strict_goal': 'goal uses a strict limit (1=yes)'
}

def features(jobs, goal, quantum, switch_cost):
    """Only quantities available before running any scheduler."""
    bursts = [p['burst'] for p in jobs]
    arrivals = [p['arrival'] for p in jobs]
    priorities = [p['priority'] for p in jobs]
    mean = sum(bursts)/len(bursts)
    return {
        'job_count': len(jobs), 'mean_burst': mean, 'max_burst': max(bursts),
        'burst_spread': sqrt(sum((b-mean)**2 for b in bursts)/len(bursts)),
        'arrival_spread': max(arrivals)-min(arrivals),
        'initial_jobs': arrivals.count(min(arrivals)),
        'target_fraction': sum(goal['group']=='all' or p['type']==goal['group'] for p in jobs)/len(jobs),
        'priority_spread': max(priorities)-min(priorities),
        'quantum': quantum, 'switch_cost': switch_cost, 'threshold': goal['threshold'],
        'metric_response': int(goal['metric']=='response'),
        'metric_waiting': int(goal['metric']=='waiting'),
        'metric_turnaround': int(goal['metric']=='turnaround'),
        'metric_ready_wait': int(goal['metric']=='max_ready_wait'),
        'average_goal': int(goal['aggregate']=='average'), 'strict_goal': int(goal['operator']=='<')
    }

def fit(rows, depth=0, max_depth=5, min_leaf=5):
    """CART-style classification: learn numeric splits minimizing Gini impurity."""
    counts = Counter(row['label'] for row in rows)
    node = {'prediction': sorted(counts, key=lambda k: (-counts[k], k))[0],
            'counts': dict(sorted(counts.items())), 'samples': len(rows)}
    if depth >= max_depth or len(counts)==1 or len(rows)<2*min_leaf:
        return node
    def impurity(counts, n):
        return n - sum(c*c for c in counts.values())/n
    best_score = impurity(counts, len(rows))
    best = None
    for name in FEATURE_LABELS:
        ordered = sorted(rows, key=lambda r:r['features'][name])
        left, right = Counter(), counts.copy()
        for i in range(1,len(ordered)):
            label = ordered[i-1]['label']; left[label]+=1; right[label]-=1
            if i<min_leaf or len(rows)-i<min_leaf:
                continue
            a,b = ordered[i-1]['features'][name], ordered[i]['features'][name]
            if a==b: continue
            score = impurity(left,i)+impurity(right,len(rows)-i)
            if score < best_score-1e-10:
                best_score=score; best=(name,(a+b)/2,ordered[:i],ordered[i:])
    if best:
        name, threshold, left, right=best
        node.update(feature=name, threshold=threshold,
                    left=fit(left,depth+1,max_depth,min_leaf),
                    right=fit(right,depth+1,max_depth,min_leaf))
    return node

def predict(tree, values):
    path=[];node=tree
    while 'feature' in node:
        key=node['feature'];left=values[key]<=node['threshold']
        path.append({'feature':key,'name':FEATURE_LABELS[key], 'value':values[key],
                     'operator':'<=' if left else '>', 'threshold':node['threshold']})
        node=node['left'] if left else node['right']
    return node,path

@lru_cache(maxsize=1)
def load_model():
    return json.loads(MODEL_PATH.read_text())

def advise(jobs, goal, quantum, switch_cost):
    model=load_model();values=features(jobs,goal,quantum,switch_cost)
    if not values['target_fraction']:
        return {'available':False,'reason':'No jobs match this goal, so the model does not make a prediction.'}
    node,path=predict(model['tree'],values)
    outside=[FEATURE_LABELS[key] for key,(low,high) in model['feature_ranges'].items()
             if not low<=values[key]<=high]
    return {'available':True,'prediction':node['prediction'],'path':path,
            'leaf_samples':node['samples'],'leaf_agreement':node['counts'][node['prediction']]/node['samples'],
            'leaf_counts':node['counts'],'features':values,'outside_training_ranges':outside,
            'evaluation':model['evaluation'],'method':'Supervised decision tree (Gini splits, depth at most 5)',
            'training_source':'240 distinct synthetic workloads labelled by the deterministic simulator; not real OS traces.'}
