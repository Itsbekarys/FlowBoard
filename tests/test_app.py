import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from flowboard.store import Store, ValidationError
from server import make_handler


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.db'
        self.store = Store(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_create_update_persist_delete(self):
        project = self.store.create_project({'name': 'Релиз'})
        task = self.store.create_task({'title': 'Проверить релиз', 'project_id': project['id']})
        changed = self.store.update_task(task['id'], {'status': 'done'})
        self.assertEqual(changed['title'], task['title'])
        self.assertEqual(changed['status'], 'done')
        self.assertTrue(any(t['id'] == task['id'] for t in Store(self.path).state()['tasks']))
        self.store.delete_task(task['id'])
        self.assertFalse(any(t['id'] == task['id'] for t in self.store.state()['tasks']))

    def test_invalid_input_is_rejected(self):
        for data in [
            {'title': '', 'project_id': 1},
            {'title': 'Task', 'project_id': 999},
            {'title': 'Task', 'project_id': True},
            {'title': 'Task', 'project_id': 1, 'status': 'invalid'},
            {'title': 'Task', 'project_id': 1, 'due_date': '2026-02-30'},
            {'title': 'x' * 161, 'project_id': 1},
        ]:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                self.store.create_task(data)

    def test_sql_characters_are_stored_as_text(self):
        title = "'); DROP TABLE tasks; --"
        task = self.store.create_task({'title': title, 'project_id': 1})
        self.assertEqual(task['title'], title)
        self.assertGreater(len(self.store.state()['tasks']), 1)

    def test_missing_task(self):
        with self.assertRaises(LookupError):
            self.store.update_task(9999, {'status': 'done'})

    def test_seed_is_not_duplicated(self):
        count = len(self.store.state()['tasks'])
        self.assertEqual(len(Store(self.path).state()['tasks']), count)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Store(Path(cls.temp.name) / 'http.db')))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def request(self, path, method='GET', data=None):
        request = Request(self.base + path, data=json.dumps(data).encode() if data is not None else None,
                          method=method, headers={'Content-Type': 'application/json'})
        return urlopen(request, timeout=5)

    def test_http_task_lifecycle(self):
        with self.request('/api/tasks', 'POST', {'title': 'HTTP task', 'project_id': 1}) as response:
            self.assertEqual(response.status, 201)
            task = json.load(response)
        with self.request(f'/api/tasks/{task["id"]}', 'PATCH', {'status': 'review'}) as response:
            self.assertEqual(json.load(response)['status'], 'review')
        with self.request(f'/api/tasks/{task["id"]}', 'DELETE') as response:
            self.assertEqual(response.status, 200)

    def test_static_files_and_health(self):
        for path in ['/', '/app.js', '/style.css', '/api/health', '/api/state']:
            with self.subTest(path=path), self.request(path) as response:
                self.assertEqual(response.status, 200)

    def test_error_statuses(self):
        for path, method, data, status in [('/api/tasks', 'POST', {'title': ''}, 400),
                                           ('/api/tasks/99999', 'PATCH', {}, 404),
                                           ('/api/missing', 'GET', None, 404)]:
            with self.subTest(path=path):
                with self.assertRaises(HTTPError) as error:
                    self.request(path, method, data)
                self.assertEqual(error.exception.code, status)


if __name__ == '__main__':
    unittest.main()
