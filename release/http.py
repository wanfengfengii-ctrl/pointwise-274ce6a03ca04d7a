import argparse
import json
import logging
import sqlite3
from contextlib import closing
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from assets.intake import freeze_asset
from assets.validation import InvalidAsset
from proofs.render import make_proof
from proofs.results import ProofRecord, load_proof
from release.database import initialize_database, open_database, write_transaction
from release.eligibility import ReleaseRejected
from release.issue import issue_release
from release.retrieval import ReleaseNotFound, get_release
from signs.assembly import create_sign, edit_sign
from signs.bindings import BindingRejected
from signs.overrides import EditRejected, effective_slot
from signs.snapshots import SignSnapshot, SignSnapshotRejected, load_current_sign_snapshot
from templates.approval import PublicationRejected, approve_and_publish
from templates.drafts import create_draft
from templates.layout import InvalidLayout


LOGGER = logging.getLogger(__name__)


class _RequestError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _RequestError(400, f'{field} must be a non-empty string')
    return value


def _require_fields(payload: dict, *fields: str) -> None:
    if payload.keys() != set(fields):
        raise _RequestError(400, 'expected fields: ' + ', '.join(fields))


def _sign_state(snapshot: SignSnapshot) -> dict:
    slots = []
    for spec in snapshot.template.slots:
        text, overridden = effective_slot(spec, snapshot.revision.overrides)
        slots.append({'key': spec.key, 'text': text, 'overridden': overridden})
    return {
        'sign': snapshot.binding.id,
        'template': snapshot.template.id,
        'assets': snapshot.binding.assets,
        'revision': snapshot.revision.id,
        'slots': slots,
    }


def _proof_state(proof: ProofRecord) -> dict:
    state = asdict(proof)
    state['overflow'] = proof.overflow
    return state


def _post(db: sqlite3.Connection, route: tuple[str, ...], payload: dict) -> tuple[int, dict]:
    match route:
        case ('assets',):
            revision = freeze_asset(db, payload)
            return 201, {'asset': revision.asset_id, 'revision': revision.id}
        case ('templates', 'drafts'):
            draft = create_draft(db, payload)
            return 201, {'draft': draft.id}
        case ('templates', 'drafts', draft_id, 'publish') if draft_id:
            if payload:
                raise _RequestError(400, 'publication expects an empty object')
            template = approve_and_publish(db, draft_id)
            return 201, {
                'template': template.id,
                'draft': template.draft,
                'title': template.title,
                'slots': [asdict(slot) for slot in template.slots],
            }
        case ('signs',):
            _require_fields(payload, 'template', 'assets')
            template_id = _identifier(payload['template'], 'template')
            assets = payload['assets']
            if not isinstance(assets, list):
                raise _RequestError(400, 'assets must be an array of asset revision numbers')
            revisions = tuple(_identifier(item, 'asset revision') for item in assets)
            return 201, _sign_state(create_sign(db, template_id, revisions))
        case ('signs', sign_id, 'edits') if sign_id:
            return 200, _sign_state(edit_sign(db, sign_id, payload))
        case ('signs', sign_id, 'proofs') if sign_id:
            _require_fields(payload, 'revision')
            revision_id = _identifier(payload['revision'], 'revision')
            return 201, _proof_state(make_proof(db, sign_id, revision_id))
        case ('signs', sign_id, 'releases') if sign_id:
            _require_fields(payload, 'proof')
            receipt = issue_release(db, sign_id, _identifier(payload['proof'], 'proof'))
            return 201, {'release': receipt.id, 'source': asdict(receipt.package.source)}
        case _:
            raise _RequestError(404, 'unknown endpoint')


def _get(db: sqlite3.Connection, route: tuple[str, ...]) -> tuple[int, dict]:
    match route:
        case ('healthz',):
            return 200, {'status': 'ok'}
        case ('signs', sign_id) if sign_id:
            return 200, _sign_state(load_current_sign_snapshot(db, sign_id))
        case ('proofs', proof_id) if proof_id:
            proof = load_proof(db, proof_id)
            if proof is None:
                raise _RequestError(404, 'unknown proof')
            return 200, _proof_state(proof)
        case ('releases', release_id) if release_id:
            receipt = get_release(db, release_id)
            return 200, {
                'release': receipt.id,
                'source': asdict(receipt.package.source),
                'html': receipt.package.html.decode('utf-8'),
            }
        case _:
            raise _RequestError(404, 'unknown endpoint')


class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        LOGGER.debug(format, *args)

    def _read_payload(self) -> dict:
        if self.headers.get('Transfer-Encoding') is not None:
            raise _RequestError(400, 'use a content length for JSON requests')
        lengths = self.headers.get_all('Content-Length', ['0'])
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal():
            raise _RequestError(400, 'invalid content length')
        try:
            length = int(lengths[0])
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise _RequestError(400, 'incomplete JSON body')
            payload = json.loads(raw.decode('utf-8'))
            if not isinstance(payload, dict):
                raise _RequestError(400, 'request body must be a JSON object')
            json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (ValueError, OverflowError, RecursionError) as error:
            raise _RequestError(400, 'invalid UTF-8 JSON body') from error
        return payload

    def _reply(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, write: bool) -> None:
        path = self.path.partition('?')[0]
        route = tuple(path[1:].split('/')) if path.startswith('/') else ()
        try:
            payload = self._read_payload() if write else None
            with closing(open_database(self.server.database_path)) as db:
                if write:
                    with write_transaction(db):
                        status, result = _post(db, route, payload)
                else:
                    db.execute('BEGIN')
                    status, result = _get(db, route)
        except (InvalidAsset, InvalidLayout) as error:
            status, result = 400, {'error': str(error)}
        except (
            _RequestError, PublicationRejected, BindingRejected, EditRejected,
            SignSnapshotRejected, ReleaseRejected, ReleaseNotFound,
        ) as error:
            status, result = error.status, {'error': str(error)}
        except sqlite3.Error as error:
            LOGGER.warning('SQLite request failed: %s', error)
            status, result = 500, {'error': 'storage operation failed'}
        self._reply(status, result)

    def do_POST(self) -> None:
        self._handle(write=True)

    def do_GET(self) -> None:
        self._handle(write=False)


class _SignServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], database_path: Path):
        self.database_path = database_path
        super().__init__(address, RequestHandler)


def serve(database_path: str | Path, host: str = '127.0.0.1', port: int = 0) -> ThreadingHTTPServer:
    path = Path(database_path)
    initialize_database(path)
    return _SignServer((host, port), path)


def main() -> None:
    parser = argparse.ArgumentParser(description='Local exhibition sign service')
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    with serve(args.db, args.host, args.port) as httpd:
        host, port = httpd.server_address[:2]
        print(f'Exhibition sign service: http://{host}:{port}', flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
