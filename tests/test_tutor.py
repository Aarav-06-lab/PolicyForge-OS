import unittest
from policyforge.tutor import answer, retrieve
from policyforge.experiments import BENCHMARK
from server import dispatch

class TutorTests(unittest.TestCase):
    def test_unseen_question_phrasings(self):
        for q,expected in [('How is the waiting time of P2 calculated?', 'waiting'),
            ('Can you explain a Round Robin turn?', 'round_robin'),
            ('Why is P4 failing my requirement?', 'failure'),
            ('Explain the Gini impurity calculation', 'gini'),
            ('Where do the training examples come from?', 'training')]:
            self.assertEqual(retrieve(q)[0],expected,q)

    def test_worked_waiting_uses_live_jobs(self):
        result=answer('Calculate P2 waiting time')
        self.assertIn('Waiting = 10 − 4 = 6.',result['steps'])
        changed=[dict(p,burst=1) if p['id']=='P2' else dict(p) for p in BENCHMARK]
        other=answer('Calculate P2 waiting time',jobs=changed)
        self.assertNotEqual(result['steps'],other['steps'])

    def test_quantum_counterfactual_is_verified(self):
        result=answer('What if quantum is 1?')
        self.assertEqual(result['table']['rows'][0], [2,2.0,5.0,6,'fail'])
        self.assertEqual(result['table']['rows'][1], [1,0.75,4.75,11,'pass'])
        self.assertEqual(result['action']['quantum'],1)

    def test_type_change_preserves_timing(self):
        result=answer('What if P4 becomes background?')
        self.assertIn('the same timeline yields goal status pass',' '.join(result['paragraphs']))
        self.assertIn(['P4',3,1,8,9,5,5],result['table']['rows'])

    def test_out_of_scope_and_followup(self):
        self.assertFalse(answer('What is the capital of France?')['supported'])
        self.assertEqual(answer('show the calculation',previous_topic='waiting')['topic'],'waiting')
        self.assertNotEqual(answer('What is Gini impurity?',previous_topic='waiting')['topic'],'waiting')

    def test_invalid_context_and_missing_process(self):
        self.assertIn('context_note',answer('What is waiting time?',jobs=[]))
        result=answer('Calculate P99 waiting time')
        self.assertIn('no P99',result['context_note'])
        self.assertNotIn('steps',result)
        self.assertIn('context_note',answer('What is waiting time?',requirement='make it fast'))

    def test_advisor_path_and_http_dispatch(self):
        result=dispatch('/api/tutor',{'question':'How does the AI decision tree predict?'})
        self.assertEqual(result['topic'],'tree')
        self.assertEqual(len(result['table']['rows']),5)
        self.assertIn('saved advisor predicts NONE',' '.join(result['paragraphs']))

    def test_validation(self):
        for q in ['',None,'a'*601]:
            with self.assertRaises(ValueError):answer(q)
        with self.assertRaises(ValueError):answer('What is waiting time?',policy='bad')

if __name__=='__main__':unittest.main()
