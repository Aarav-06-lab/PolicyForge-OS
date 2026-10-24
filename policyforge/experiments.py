"""Small requirement grammar and seeded counterexample search; no LLM dependency."""
import random
import re
from .core import simulate, POLICIES
from .advisor import advise

BENCHMARK = [
    {'id': 'P1', 'arrival': 0, 'burst': 8, 'priority': 3, 'type': 'batch'},
    {'id': 'P2', 'arrival': 1, 'burst': 4, 'priority': 1, 'type': 'interactive'},
    {'id': 'P3', 'arrival': 2, 'burst': 2, 'priority': 2, 'type': 'interactive'},
    {'id': 'P4', 'arrival': 3, 'burst': 1, 'priority': 1, 'type': 'interactive'}]

def parse_goal(text):
    if not isinstance(text, str) or len(text) > 300:
        raise ValueError('Enter a requirement of at most 300 characters.')
    s = text.lower().strip()
    # Restrict interpretation rather than silently accepting unsupported clauses.
    patterns = [
        (r'(interactive|batch|background|all) (?:jobs|tasks|processes) (?:must |should )?(?:start|respond) within (\d+) (?:time )?units?\.?', 'response', 'each', '<='),
        (r'average (waiting|turnaround|response) time (?:must |should )?(?:be |remain )?(below|under|at most) (\d+) (?:time )?units?\.?', None, 'average', None),
        (r'no ready process (?:may |should )?wait longer than (\d+) (?:time )?units?\.?', 'max_ready_wait', 'each', '<=')]
    for pattern, metric, aggregate, op in patterns:
        m = re.fullmatch(pattern, s)
        if not m:
            continue
        if metric == 'response':
            group, threshold = m.groups()
        elif metric == 'max_ready_wait':
            group, threshold = 'all', m.group(1)
        else:
            metric, operator, threshold = m.groups()
            group, op = 'all', '<=' if operator == 'at most' else '<'
        threshold = int(threshold)
        if threshold > 10000:
            raise ValueError('Use a threshold between 0 and 10000.')
        return {'metric': metric, 'group': group, 'aggregate': aggregate, 'operator': op, 'threshold': threshold}
    raise ValueError('Use one supported measurable goal, for example: interactive jobs must start within 2 units. Multiple clauses and unbounded starvation claims are not supported.')

def verify(result, goal):
    rows = [p for p in result['processes'] if goal['group'] == 'all' or p['type'] == goal['group']]
    if not rows:
        return {'status': 'not_applicable', 'value': None, 'violations': [], 'explanation': 'No processes belong to the target group.'}
    metric, threshold = goal['metric'], goal['threshold']
    passes = lambda v: v <= threshold if goal['operator'] == '<=' else v < threshold
    value = sum(p[metric] for p in rows)/len(rows) if goal['aggregate'] == 'average' else max(p[metric] for p in rows)
    violations = [] if passes(value) else ([{'id': 'workload average', 'value': value}] if goal['aggregate'] == 'average' else [{'id': p['id'], 'value': p[metric]} for p in rows if not passes(p[metric])])
    description = 'average' if goal['aggregate'] == 'average' else 'maximum'
    return {'status': 'pass' if passes(value) else 'fail', 'value': value, 'violations': violations,
            'explanation': f"Measured {description} {metric.replace('_', ' ')}: {value:g}; required {goal['operator']} {threshold}."}

def compare(jobs, goal, quantum=2, switch_cost=0, include_advisor=True):
    runs = []
    for policy in POLICIES:
        result = simulate(jobs, policy, quantum, switch_cost)
        result['check'] = verify(result, goal)
        runs.append(result)
    passing = [r for r in runs if r['check']['status'] == 'pass']
    best = min(passing, key=lambda r: (r['avg_waiting'], r['switches'])) if passing else None
    advice = advise(jobs, goal, quantum, switch_cost) if include_advisor else {'available': False, 'reason': 'Inference disabled during dataset generation.'}
    if advice['available']:
        actual = best['policy'] if best else 'NONE'
        predicted_run = next((r for r in runs if r['policy'] == advice['prediction']), None)
        advice.update(actual_choice=actual, agrees_with_simulation=advice['prediction']==actual,
                      predicted_goal_status=predicted_run['check']['status'] if predicted_run else None)
    if all(r['check']['status'] == 'not_applicable' for r in runs):
        recommendation = 'This goal does not apply: no jobs match its target group. Add a matching job or choose a goal for all jobs.'
    elif best:
        recommendation = f"{best['policy']} meets this goal on this workload and has the lowest average waiting time among passing candidates."
    else:
        recommendation = 'None of these four configurations meets this goal. Try a smaller RR quantum or revise the workload or goal.'
    return {'goal': goal, 'runs': runs, 'recommendation': recommendation, 'advisor': advice}

def break_scheduler(policy, goal, quantum=2, switch_cost=0, seed=42, budget=100):
    if type(seed) is not int or type(budget) is not int or not 1 <= budget <= 1000:
        raise ValueError('Use an integer seed and a search budget from 1 to 1000.')
    rng = random.Random(seed)
    for attempt in range(1, budget+1):
        jobs = []
        profile = rng.choice(('convoy', 'burst', 'mixed'))
        for i in range(rng.randint(3, 10)):
            kind = rng.choice(('interactive', 'batch', 'background'))
            if i == 1 and goal['group'] != 'all':
                kind = goal['group']
            jobs.append({'id': f'P{i+1}', 'arrival': 0 if profile == 'burst' else rng.randint(0, 10),
                         'burst': rng.randint(1, 12), 'priority': rng.randint(1, 5), 'type': kind})
        if profile == 'convoy':
            jobs[0].update(arrival=0, burst=20, type='batch')
            for p in jobs[1:]: p['arrival'] = rng.randint(1, 5)
        def fails(candidate):
            return verify(simulate(candidate, policy, quantum, switch_cost), goal)['status'] == 'fail'
        if not fails(jobs):
            continue
        original_count = len(jobs)
        # Greedy deletion: 1-minimal in process count, not a global minimum.
        changed = True
        while changed and len(jobs) > 1:
            changed = False
            for i in range(len(jobs)):
                candidate = jobs[:i] + jobs[i+1:]
                if fails(candidate):
                    jobs = candidate; changed = True; break
        result = simulate(jobs, policy, quantum, switch_cost)
        return {'found': True, 'seed': seed, 'attempts': attempt, 'budget': budget, 'profile': profile,
                'original_count': original_count, 'jobs': jobs, 'result': result, 'check': verify(result, goal),
                'comparison': compare(jobs, goal, quantum, switch_cost)}
    return {'found': False, 'seed': seed, 'attempts': budget, 'budget': budget,
            'explanation': 'No failure found within this test budget. This is not a guarantee for other workloads.'}
