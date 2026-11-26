import json
import unittest
from contextlib import ExitStack, closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from release.database import open_database
from release.http import serve


@dataclass(frozen=True)
class Reply:
    status: int
    body: dict
    raw: bytes


class Client:
    def __init__(self, base: str):
        self.base = base

    def request(self, path: str, payload: dict | None = None) -> Reply:
        request = Request(self.base + path)
        if payload is not None:
            request.data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            request.add_header('Content-Type', 'application/json')
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            return Reply(response.status, json.loads(raw), raw)


@contextmanager
def running_service(path: Path):
    with serve(path) as server:
        host, port = server.server_address[:2]
        thread = Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05})
        thread.start()
        try:
            yield Client(f'http://{host}:{port}')
        finally:
            server.shutdown()
            thread.join()


def two_slots() -> list[dict]:
    return [
        {'key': 'A', 'label': '右栏', 'default': '河岸', 'width': 2, 'max_lines': 2},
        {'key': 'B', 'label': '桥栏', 'default': '木桥', 'width': 2, 'max_lines': 2},
    ]


class HTTPCase(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.path = Path(stack.enter_context(TemporaryDirectory())) / 'test.sqlite3'
        self.service = stack.enter_context(ExitStack())
        self.client = self.service.enter_context(running_service(self.path))

    def restart(self):
        self.service.close()
        self.client = self.service.enter_context(running_service(self.path))

    def api(self, path, payload=None, *, status=200) -> dict:
        reply = self.client.request(path, payload)
        self.assertEqual(reply.status, status, reply.body)
        return reply.body

    def publish(self, slots=None, *, title='河岸记忆') -> dict:
        draft = self.api('/templates/drafts', {
            'title': title,
            'slots': two_slots() if slots is None else slots,
        }, status=201)
        return self.api(f"/templates/drafts/{draft['draft']}/publish", {}, status=201)

    def sign(self, template=None, assets=()) -> dict:
        if template is None:
            template = self.publish()['template']
        return self.api('/signs', {'template': template, 'assets': list(assets)}, status=201)

    def edit(self, sign, key, op, *, text=None) -> dict:
        payload = {'key': key, 'op': op}
        if text is not None:
            payload['text'] = text
        return self.api(f"/signs/{sign['sign']}/edits", payload)

    def proof(self, sign) -> dict:
        return self.api(
            f"/signs/{sign['sign']}/proofs", {'revision': sign['revision']}, status=201,
        )

    def issue(self, sign, proof, *, status=201) -> dict:
        return self.api(f"/signs/{sign['sign']}/releases", {'proof': proof['proof']}, status=status)

    def count(self, table: str) -> int:
        with closing(open_database(self.path)) as db:
            return db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

    def block_commit_after(self, table: str, event: str) -> None:
        supported = {
            ('releases', 'INSERT'),
            ('sign_current', 'UPDATE'),
            ('signs', 'UPDATE'),
            ('sign_revisions', 'INSERT'),
            ('template_drafts', 'INSERT'),
            ('published_templates', 'INSERT'),
            ('template_lineage', 'INSERT'),
        }
        if (table, event) not in supported:
            raise ValueError('unsupported regression trigger')
        with closing(open_database(self.path)) as db:
            db.executescript(f'''
                CREATE TABLE commit_test_parent (id INTEGER PRIMARY KEY);
                CREATE TABLE commit_test_child (
                    parent INTEGER NOT NULL REFERENCES commit_test_parent(id)
                    DEFERRABLE INITIALLY DEFERRED
                );
                CREATE TRIGGER reject_test_commit AFTER {event} ON {table}
                BEGIN
                    INSERT INTO commit_test_child(parent) VALUES (1);
                END;
            ''')

    def unblock_commit(self) -> None:
        with closing(open_database(self.path)) as db:
            db.execute('DROP TRIGGER reject_test_commit')


def scenario(case_id, input_data, expected, actual, downstream_expected, downstream_actual,
             code_paths, oracle):
    evidence = {
        'case_id': case_id,
        'input': input_data,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': code_paths,
        'oracle': oracle,
    }
    print('POINTWISE_SCENARIO ' + json.dumps(evidence, ensure_ascii=False), flush=True)
