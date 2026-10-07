"""Exercise the learning HTTP contract against an isolated database."""
import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class LearningHTTPTests(unittest.TestCase):
    def test_save_reload_conflict_attempt_and_export(self):
        spec = importlib.util.spec_from_file_location('isolated_learning_app', ROOT / 'server.py')
        app = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(app)
        with tempfile.TemporaryDirectory() as directory:
            app.DATA = Path(directory)
            app.DB_PATH = app.DATA / 'test.sqlite'
            app.initialize()
            (app.DATA / 'curriculum.json').write_text(json.dumps({'items': [{'id': 'dsa:one', 'kind': 'dsa'}]}))
            (app.DATA / 'plan.json').write_text(json.dumps({'days': [{'day': 1, 'title': 'Original session'}]}))

            class QuietHandler(app.Handler):
                def log_message(self, *args):
                    pass

            http = app.ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()

            def request(path, body=None):
                req = Request(f'http://127.0.0.1:{http.server_port}' + path,
                              data=json.dumps(body).encode() if body is not None else None,
                              headers={'Content-Type': 'application/json'})
                with urlopen(req, timeout=5) as response:
                    return json.load(response)

            try:
                payload = {'id': 'dsa:one', 'status': 'practised', 'notes': 'Keep my reasoning', 'evidence': 'local artifact', 'version': 0}
                request('/api/learning/state', payload)
                with self.assertRaises(HTTPError) as conflict:
                    request('/api/learning/state', payload)
                self.assertEqual(conflict.exception.code, 409)
                conflict.exception.close()
                attempt = {'id': 'dsa:one', 'day': 1, 'outcome': 'assisted', 'minutes': 25, 'hints': 1, 'client_nonce': 'same-request'}
                request('/api/learning/attempt', attempt)
                request('/api/learning/attempt', attempt)
                request('/api/prep-state', {'day': 1, 'state': {'tasks': [0], 'notes': 'Next step'}})
                (app.DATA / 'plan.json').write_text(json.dumps({'days': [{'day': 1, 'title': 'New default'}]}))
                app.initialize()
                result = request('/api/export')
                self.assertEqual(result['learning']['states']['dsa:one']['notes'], payload['notes'])
                self.assertEqual(result['learning']['states']['dsa:one']['status'], 'practised')
                self.assertEqual(len(result['learning']['attempts']), 1)
                self.assertEqual([r['due_day'] for r in result['learning']['retries']], [3, 8, 15])
                self.assertEqual(result['plan']['days'][0]['title'], 'Original session')
                self.assertEqual(result['prep_state']['1']['notes'], 'Next step')
            finally:
                http.shutdown()
                thread.join()
                http.server_close()


if __name__ == '__main__':
    unittest.main()
