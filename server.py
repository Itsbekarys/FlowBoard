"""FlowBoard HTTP entry point. Run with python server.py."""
import json
import os
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from flowboard.store import Store, ValidationError

ROOT = Path(__file__).parent


def make_handler(store):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT / 'web'), **kwargs)

        def respond(self, status, data):
            payload = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/api/state':
                self.respond(200, store.state())
            elif path == '/api/health':
                self.respond(200, {'status': 'ok'})
            elif path.startswith('/api/'):
                self.respond(404, {'error': 'Маршрут не найден'})
            else:
                super().do_GET()

        def mutate(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > 65536:
                    raise ValidationError('Слишком большой запрос')
                data = json.loads(self.rfile.read(length) or b'{}')
                if not isinstance(data, dict):
                    raise ValidationError('Ожидается объект JSON')
                parts = urlsplit(self.path).path.strip('/').split('/')
                if parts == ['api', 'tasks'] and self.command == 'POST':
                    result = store.create_task(data)
                elif parts == ['api', 'projects'] and self.command == 'POST':
                    result = store.create_project(data)
                elif len(parts) == 3 and parts[:2] == ['api', 'tasks']:
                    task_id = int(parts[2])
                    if self.command == 'PATCH':
                        result = store.update_task(task_id, data)
                    elif self.command == 'DELETE':
                        result = store.delete_task(task_id)
                    else:
                        self.respond(405, {'error': 'Метод не поддерживается'})
                        return
                else:
                    self.respond(404, {'error': 'Маршрут не найден'})
                    return
                self.respond(201 if self.command == 'POST' else 200, result)
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                self.respond(400, {'error': str(exc)})
            except LookupError as exc:
                self.respond(404, {'error': str(exc)})
            except sqlite3.Error:
                self.respond(500, {'error': 'Не удалось сохранить изменения'})

        do_POST = mutate
        do_PATCH = mutate
        do_DELETE = mutate

    return Handler


if __name__ == '__main__':
    store = Store(os.getenv('FLOWBOARD_DB', str(ROOT / 'data' / 'flowboard.db')))
    host, port = os.getenv('HOST', '127.0.0.1'), int(os.getenv('PORT', '8000'))
    server = ThreadingHTTPServer((host, port), make_handler(store))
    print(f'FlowBoard: http://{host}:{port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
