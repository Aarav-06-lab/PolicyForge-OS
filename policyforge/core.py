"""Deterministic, single-CPU scheduling. All values are simulated time units."""
from collections import deque

POLICIES = ('FCFS', 'SJF', 'Priority', 'RR')

def validate(jobs):
    if not isinstance(jobs, list) or not 1 <= len(jobs) <= 60:
        raise ValueError('Enter between 1 and 60 processes.')
    ids = set()
    for p in jobs:
        if not isinstance(p, dict) or not isinstance(p.get('id'), str) or not p['id'].strip() or len(p['id']) > 24 or p['id'] in ids:
            raise ValueError('Each process needs a unique ID of 1–24 characters.')
        ids.add(p['id'])
        for field, low, high in [('arrival', 0, 1000), ('burst', 1, 1000), ('priority', 1, 99)]:
            if type(p.get(field)) is not int or not low <= p[field] <= high:
                raise ValueError(f'{field} must be an integer between {low} and {high}.')
        if p.get('type') not in ('interactive', 'batch', 'background'):
            raise ValueError('Type must be interactive, batch or background.')

def simulate(jobs, policy, quantum=2, switch_cost=0):
    validate(jobs)
    if policy not in POLICIES:
        raise ValueError('Unsupported scheduler.')
    if type(quantum) is not int or not 1 <= quantum <= 100:
        raise ValueError('Quantum must be an integer from 1 to 100.')
    if type(switch_cost) is not int or not 0 <= switch_cost <= 10:
        raise ValueError('Switch cost must be an integer from 0 to 10.')
    pending = sorted((dict(p) for p in jobs), key=lambda p: (p['arrival'], p['id']))
    remaining = {p['id']: p['burst'] for p in pending}
    ready, trace, first, completion = deque(), [], {}, {}
    t, i, switches, previous = 0, 0, 0, None
    def admit():
        nonlocal i
        while i < len(pending) and pending[i]['arrival'] <= t:
            ready.append(pending[i]); i += 1
    while len(completion) < len(jobs):
        admit()
        if not ready:
            next_t = pending[i]['arrival']
            if next_t > t:
                trace.append({'id': 'IDLE', 'start': t, 'end': next_t, 'kind': 'idle'})
            t = next_t
            admit()
        if policy in ('SJF', 'Priority'):
            field = 'burst' if policy == 'SJF' else 'priority'
            p = min(ready, key=lambda p: (p[field], p['arrival'], p['id']))
            ready.remove(p)
        else:
            p = ready.popleft()
        pid = p['id']
        if previous is not None and previous != pid:
            switches += 1
            if switch_cost:
                trace.append({'id': 'SWITCH', 'start': t, 'end': t + switch_cost, 'kind': 'overhead'})
                t += switch_cost
                admit()
        first.setdefault(pid, t)
        duration = min(remaining[pid], quantum) if policy == 'RR' else remaining[pid]
        trace.append({'id': pid, 'start': t, 'end': t + duration, 'kind': 'run'})
        t += duration; remaining[pid] -= duration
        admit()  # Arrivals at a quantum endpoint precede the requeued process.
        if remaining[pid]:
            ready.append(p)
        else:
            completion[pid] = t
        previous = pid
    rows = []
    for p in pending:
        pid = p['id']; end = completion[pid]
        slices = [s for s in trace if s['kind'] == 'run' and s['id'] == pid]
        gaps = [slices[0]['start'] - p['arrival']]
        gaps += [b['start'] - a['end'] for a, b in zip(slices, slices[1:])]
        rows.append({**p, 'completion': end, 'turnaround': end-p['arrival'],
                     'waiting': end-p['arrival']-p['burst'], 'response': first[pid]-p['arrival'],
                     'max_ready_wait': max(gaps)})
    # Invariants describe simulator correctness, separately from user goals.
    assert all(a['end'] <= b['start'] for a, b in zip(trace, trace[1:]))
    for p in rows:
        slices = [s for s in trace if s['kind'] == 'run' and s['id'] == p['id']]
        assert sum(s['end']-s['start'] for s in slices) == p['burst']
        assert all(s['start'] >= p['arrival'] and s['end'] > s['start'] for s in slices)
        assert min(p['waiting'], p['response']) >= 0
    elapsed = t - pending[0]['arrival']
    return {'policy': policy, 'quantum': quantum, 'switch_cost': switch_cost, 'trace': trace, 'processes': rows,
            'avg_waiting': sum(p['waiting'] for p in rows)/len(rows),
            'avg_turnaround': sum(p['turnaround'] for p in rows)/len(rows),
            'avg_response': sum(p['response'] for p in rows)/len(rows),
            'switches': switches, 'finish': t, 'throughput': len(rows)/elapsed,
            'utilization': 100*sum(p['burst'] for p in rows)/elapsed}
