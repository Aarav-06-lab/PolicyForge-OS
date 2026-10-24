"""Check the learned model, evaluation split and deterministic verification."""
import json
from pathlib import Path
import unittest
from policyforge.advisor import features, fit, predict, advise, load_model
from policyforge.experiments import BENCHMARK, compare, parse_goal

ROOT=Path(__file__).resolve().parents[1]

class AdvisorTests(unittest.TestCase):
    def test_tree_learns_a_split_from_examples(self):
        goal=parse_goal('all jobs must start within 2 units')
        values=features(BENCHMARK,goal,2,0)
        rows=[{'features':dict(values,job_count=n),'label':'FCFS' if n<10 else 'RR'} for n in range(1,21)]
        tree=fit(rows)
        self.assertEqual(predict(tree,dict(values,job_count=3))[0]['prediction'],'FCFS')
        self.assertEqual(predict(tree,dict(values,job_count=17))[0]['prediction'],'RR')
        self.assertIn('feature',tree)

    def test_saved_model_and_holdout_metrics_are_reproducible(self):
        rows=json.loads((ROOT/'data/advisor_dataset.json').read_text())
        train=[r for r in rows if r['split']=='train'];test=[r for r in rows if r['split']=='test']
        self.assertEqual((len(train),len(test)),(192,48))
        self.assertTrue(set(r['id'] for r in train).isdisjoint(r['id'] for r in test))
        self.assertEqual(len({json.dumps(r['jobs'],sort_keys=True) for r in rows}),240)
        model=load_model()
        self.assertEqual(fit(train),model['tree'])
        correct=sum(predict(model['tree'],r['features'])[0]['prediction']==r['label'] for r in test)
        self.assertEqual(correct,model['evaluation']['correct'])
        self.assertEqual(correct/len(test),model['evaluation']['accuracy'])

    def test_training_labels_and_features_match_simulator(self):
        rows=json.loads((ROOT/'data/advisor_dataset.json').read_text())
        for row in rows:
            self.assertEqual(features(row['jobs'],row['goal'],row['quantum'],row['switch_cost']),row['features'])
            result=compare(row['jobs'],row['goal'],row['quantum'],row['switch_cost'],include_advisor=False)
            passing=[r for r in result['runs'] if r['check']['status']=='pass']
            best=min(passing,key=lambda r:(r['avg_waiting'],r['switches'])) if passing else None
            self.assertEqual(row['label'],best['policy'] if best else 'NONE')
            self.assertTrue(all('avg_waiting' not in r['features'] for r in [row]))

    def test_advice_is_checked_and_handles_missing_target(self):
        goal=parse_goal('interactive jobs must start within 2 units')
        for q in [1,2]:
            result=compare(BENCHMARK,goal,q)
            advisor=result['advisor']
            self.assertTrue(advisor['available'])
            self.assertEqual(advisor['actual_choice'],'RR' if q==1 else 'NONE')
            self.assertEqual(advisor['agrees_with_simulation'],advisor['prediction']==advisor['actual_choice'])
            self.assertTrue(advisor['path'])
        self.assertFalse(advise([BENCHMARK[0]],goal,2,0)['available'])
        odd=[dict(p,burst=100) for p in BENCHMARK]
        self.assertTrue(advise(odd,goal,2,0)['outside_training_ranges'])

if __name__=='__main__':unittest.main()
