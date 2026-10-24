import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from policyforge.llm_tutor import generate_explanation, model_status
from server import dispatch

class Response:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,size):
        return json.dumps({'output':[{'type':'message','content':[{'type':'output_text','text':'Response time is the first start minus arrival.'}]}]}).encode()

class GenerativeTutorTests(unittest.TestCase):
    @patch.dict('os.environ',{},clear=True)
    def test_missing_key_never_calls_provider(self):
        self.assertFalse(model_status()['configured'])
        with patch('urllib.request.urlopen') as request:
            result=dispatch('/api/tutor',{'question':'What is waiting time?','mode':'generative'})
            self.assertIn('not configured',result['model_note'])
            self.assertTrue(result['supported']);request.assert_not_called()

    @patch.dict('os.environ',{'OPENAI_API_KEY':'unit-test-placeholder'},clear=True)
    def test_request_uses_verified_context_and_does_not_expose_key(self):
        with patch('urllib.request.urlopen',return_value=Response()) as request:
            result=generate_explanation('Explain response time',{'steps':['Response = 2 − 1 = 1.']},[{'role':'system','content':'bad'},{'role':'user','content':'Earlier question'}])
            req=request.call_args.args[0];body=json.loads(req.data)
            self.assertEqual(req.full_url,'https://api.openai.com/v1/responses')
            self.assertFalse(body['store']);self.assertEqual(body['max_output_tokens'],650)
            self.assertEqual(body['input'][0]['role'],'user')
            self.assertIn('verified_lab_context',body['input'][-1]['content'])
            self.assertEqual(result['model'],'gpt-4.1-mini')
            self.assertFalse(result['verified'])
            self.assertNotIn('unit-test-placeholder',json.dumps(result))

    @patch.dict('os.environ',{'OPENAI_API_KEY':'unit-test-placeholder'},clear=True)
    def test_provider_error_retains_local_answer(self):
        error=HTTPError('https://api.openai.com/v1/responses',401,'Unauthorized',{},None)
        with patch('urllib.request.urlopen',side_effect=error):
            result=dispatch('/api/tutor',{'question':'What is waiting time?','mode':'generative'})
            self.assertIn('HTTP 401',result['model_note'])
            self.assertTrue(result['steps'])
            self.assertNotIn('generative',result)

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):dispatch('/api/tutor',{'question':'What is waiting time?','mode':'unknown'})

if __name__=='__main__':unittest.main()

class GeminiTutorTests(unittest.TestCase):
    @patch.dict('os.environ',{'GEMINI_API_KEY':'test-gemini-placeholder','GEMINI_MODEL':'gemini-2.5-flash'},clear=True)
    def test_gemini_request_and_response(self):
        class GeminiResponse(Response):
            def read(self,size):return json.dumps({'candidates':[{'content':{'parts':[{'text':'Internal thought','thought':True},{'text':'P2 waits for six time units.'}]}}]}).encode()
        self.assertEqual(model_status()['provider'],'Gemini')
        with patch('urllib.request.urlopen',return_value=GeminiResponse()) as request:
            result=generate_explanation('Why?',{'steps':['Waiting = 6.']},[{'role':'assistant','content':'Earlier answer'}])
            req=request.call_args.args[0];body=json.loads(req.data)
            self.assertIn('gemini-2.5-flash:generateContent',req.full_url)
            self.assertNotIn('test-gemini-placeholder',req.full_url)
            self.assertEqual(body['contents'][0]['role'],'model')
            self.assertIn('verified_lab_context',body['contents'][-1]['parts'][0]['text'])
            self.assertEqual(result['provider'],'Gemini')
            self.assertNotIn('Internal thought',result['text'])
            self.assertIn('six',result['text'])

    @patch.dict('os.environ',{'GEMINI_API_KEY':'test-gemini-placeholder','OPENAI_API_KEY':'test-openai-placeholder','AI_PROVIDER':'openai'},clear=True)
    def test_explicit_provider_overrides_auto_detection(self):
        self.assertEqual(model_status()['provider'],'OpenAI')

class TLSConfigurationTests(unittest.TestCase):
    def test_certificate_verification_stays_enabled(self):
        import ssl
        from policyforge.llm_tutor import tls_context
        context=tls_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)
