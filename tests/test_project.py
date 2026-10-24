import random
import unittest
from policyforge.core import simulate, validate, POLICIES
from policyforge.experiments import BENCHMARK, parse_goal, verify, break_scheduler, compare
from server import dispatch

GOAL = 'interactive jobs must start within 2 units'

class SchedulingTests(unittest.TestCase):
    def test_review_baselines(self):
        expected = {'FCFS': (7, 10.75, 7, 3, 11), 'SJF': (5.5, 9.25, 5.5, 3, 10),
                    'Priority': (6.75, 10.5, 6.75, 3, 11), 'RR': (5, 8.75, 2, 6, 5)}
        for policy, values in expected.items():
            r = simulate(BENCHMARK, policy)
            actual = (r['avg_waiting'], r['avg_turnaround'], r['avg_response'], r['switches'],
                      max(p['response'] for p in r['processes'] if p['type']=='interactive'))
            self.assertEqual(actual, values)
            self.assertEqual(r['finish'], 15)
        self.assertEqual([p['waiting'] for p in simulate(BENCHMARK,'FCFS')['processes']], [0,7,10,11])
        self.assertEqual([p['waiting'] for p in simulate(BENCHMARK,'SJF')['processes']], [0,10,7,5])

    def test_rr_endpoint_order_and_quantum_sweep(self):
        expected = {1: (4.75,.75,2,11,'pass'), 2:(5,2,5,6,'fail'), 4:(5.75,4,7,4,'fail'),8:(7,7,11,3,'fail')}
        for q, values in expected.items():
            r = simulate(BENCHMARK,'RR',q)
            actual = (r['avg_waiting'],r['avg_response'],max(p['response'] for p in r['processes'] if p['type']=='interactive'),r['switches'],verify(r,parse_goal(GOAL))['status'])
            self.assertEqual(actual,values)
        r = simulate(BENCHMARK,'RR',2)
        self.assertEqual([p['response'] for p in r['processes']],[0,1,2,5])
        self.assertEqual([(s['id'],s['start'],s['end']) for s in r['trace']], [('P1',0,2),('P2',2,4),('P3',4,6),('P1',6,8),('P4',8,9),('P2',9,11),('P1',11,13),('P1',13,15)])

    def test_idle_and_ties(self):
        jobs = [dict(BENCHMARK[0],id='B',arrival=3,burst=2,priority=1),dict(BENCHMARK[0],id='A',arrival=3,burst=1,priority=1)]
        r = simulate(jobs,'Priority')
        self.assertEqual(r['trace'][0],{'id':'IDLE','kind':'idle','start':0,'end':3})
        self.assertEqual(r['trace'][1]['id'],'A')
        self.assertEqual(r['utilization'],100)

    def test_switch_overhead(self):
        jobs = [dict(BENCHMARK[0],burst=2),dict(BENCHMARK[1],arrival=0,burst=1)]
        r = simulate(jobs,'RR',1,1)
        self.assertEqual(r['switches'],2)
        self.assertEqual(r['finish'],5)
        self.assertEqual(r['utilization'],60)
        self.assertEqual([p['response'] for p in r['processes']],[0,2])
        r = simulate([jobs[0]],'RR',1,1)
        self.assertEqual(r['switches'],0)
        self.assertEqual(r['finish'],2)

    def test_no_mutation(self):
        before = [dict(p) for p in BENCHMARK]
        for policy in POLICIES: simulate(BENCHMARK,policy)
        self.assertEqual(before,BENCHMARK)

    def test_invalid_workloads(self):
        cases = [[],[dict(BENCHMARK[0],burst=0)],[dict(BENCHMARK[0],arrival=-1)],
                 [dict(BENCHMARK[0],burst=True)],[BENCHMARK[0],BENCHMARK[0]],
                 [dict(BENCHMARK[0],type='unknown')]]
        for jobs in cases:
            with self.assertRaises(ValueError): validate(jobs)
        for args in [('unknown',2,0),('RR',0,0),('RR',2,-1)]:
            with self.assertRaises(ValueError): simulate(BENCHMARK,*args)

    def test_seeded_workload_invariants(self):
        rng = random.Random(2026)
        for _ in range(100):
            jobs=[{'id':str(i),'arrival':rng.randint(0,30),'burst':rng.randint(1,15),'priority':rng.randint(1,5),'type':rng.choice(['interactive','batch','background'])} for i in range(rng.randint(1,12))]
            for policy in POLICIES:
                r=simulate(jobs,policy,rng.randint(1,5),rng.randint(0,2))
                self.assertEqual(len(r['processes']),len(jobs))
                self.assertLessEqual(r['utilization'],100)

class RequirementTests(unittest.TestCase):
    def test_supported_phrases(self):
        self.assertEqual(parse_goal(GOAL),{'metric':'response','group':'interactive','aggregate':'each','operator':'<=','threshold':2})
        self.assertEqual(parse_goal('average waiting time below 7 units')['operator'],'<')
        self.assertEqual(parse_goal('average response time at most 2 units')['operator'],'<=')
        self.assertEqual(parse_goal('no ready process may wait longer than 10 units')['metric'],'max_ready_wait')

    def test_ambiguous_and_compound_rejected(self):
        for text in ['make it fast','interactive jobs must start soon',GOAL+' and background tasks should not starve','average response time below -2 units','all jobs must start within 10001 units']:
            with self.assertRaises(ValueError): parse_goal(text)

    def test_average_does_not_hide_individual_failure(self):
        r=simulate(BENCHMARK,'RR')
        self.assertEqual(verify(r,parse_goal('average response time at most 2 units'))['status'],'pass')
        self.assertEqual(verify(r,parse_goal(GOAL))['violations'],[{'id':'P4','value':5}])

    def test_absent_group(self):
        self.assertEqual(verify(simulate([BENCHMARK[0]],'FCFS'),parse_goal(GOAL))['status'],'not_applicable')

class ExperimentTests(unittest.TestCase):
    def test_search_reproducible_reduced_and_replayable(self):
        goal=parse_goal(GOAL)
        a=break_scheduler('RR',goal,1,seed=42,budget=100)
        b=break_scheduler('RR',goal,1,seed=42,budget=100)
        self.assertEqual(a,b)
        self.assertTrue(a['found'])
        self.assertEqual(verify(simulate(a['jobs'],'RR',1),goal)['status'],'fail')
        for i in range(len(a['jobs'])):
            reduced=a['jobs'][:i]+a['jobs'][i+1:]
            if reduced:self.assertNotEqual(verify(simulate(reduced,'RR',1),goal)['status'],'fail')

    def test_no_failure_is_not_guarantee(self):
        r=break_scheduler('RR',parse_goal('all jobs must start within 10000 units'),seed=8,budget=15)
        self.assertFalse(r['found'])
        self.assertEqual(r['attempts'],15)

    def test_comparison_with_no_matching_jobs(self):
        result = compare([BENCHMARK[0]], parse_goal(GOAL))
        self.assertTrue(all(r['check']['status'] == 'not_applicable' for r in result['runs']))
        self.assertIn('no jobs match', result['recommendation'])
        self.assertNotIn('smaller RR quantum', result['recommendation'])

    def test_api_dispatch(self):
        data={'requirement':GOAL,'jobs':BENCHMARK,'quantum':1}
        result=dispatch('/api/compare',data)
        self.assertEqual(len(result['runs']),4)
        self.assertEqual(result['runs'][-1]['check']['status'],'pass')
        self.assertTrue(dispatch('/api/break',{**data,'budget':100})['found'])

if __name__=='__main__': unittest.main()
