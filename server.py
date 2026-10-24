"""Run with python3 server.py. No third-party packages required."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from policyforge.experiments import BENCHMARK, compare, parse_goal, break_scheduler
from policyforge.tutor import answer as tutor_answer
from policyforge.llm_tutor import model_status, generate_explanation

ROOT = Path(__file__).parent / 'web'

def dispatch(path, data):
    if path == '/api/tutor':
        mode = data.get('mode', 'local')
        if mode not in ('local', 'generative'):
            raise ValueError('Choose local or generative tutor mode.')
        result = tutor_answer(data.get('question'), data.get('jobs', BENCHMARK),
                              data.get('requirement', 'interactive jobs must start within 2 units'),
                              data.get('quantum', 2), data.get('switch_cost', 0),
                              data.get('policy', 'RR'), data.get('previous_topic'))
        if mode == 'generative':
            try:
                result['generative'] = generate_explanation(data['question'], result, data.get('history'))
            except ValueError as exc:
                result['model_note'] = str(exc)
        return result
    goal = parse_goal(data.get('requirement', ''))
    options = {'quantum': data.get('quantum', 2), 'switch_cost': data.get('switch_cost', 0)}
    if path == '/api/compare':
        return compare(data.get('jobs', BENCHMARK), goal, **options)
    if path == '/api/break':
        return break_scheduler(data.get('policy', 'RR'), goal, seed=data.get('seed', 42), budget=data.get('budget', 100), **options)
    raise ValueError('Unknown endpoint.')

class Handler(BaseHTTPRequestHandler):
    def respond(self, code, value):
        body = json.dumps(value).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        files = {'/': ('index.html', 'text/html'), '/tutor': ('tutor.html', 'text/html'), '/about': ('about.html', 'text/html'), '/common.js': ('common.js', 'text/javascript'), '/app.js': ('app.js', 'text/javascript'), '/tutor-page.js': ('tutor-page.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        route = self.path.split('?', 1)[0]
        if route == '/api/tutor/status':
            return self.respond(200, model_status())
        if route == '/api/benchmark':
            return self.respond(200, BENCHMARK)
        if route not in files:
            return self.respond(404, {'error': 'Not found'})
        name, mime = files[route]; body = (ROOT/name).read_bytes()
        self.send_response(200); self.send_header('Content-Type', mime+'; charset=utf-8'); self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 100000:
                raise ValueError('Request must contain JSON smaller than 100 KB.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict): raise ValueError('Expected a JSON object.')
            self.respond(200, dispatch(self.path, data))
        except (ValueError, TypeError, KeyError) as e:
            self.respond(400, {'error': str(e)})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the local PolicyForge scheduling lab.')
    parser.add_argument('--port', type=int, default=8765, help='Local port (default: 8765)')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    print(f'PolicyForge AI → http://127.0.0.1:{args.port}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
