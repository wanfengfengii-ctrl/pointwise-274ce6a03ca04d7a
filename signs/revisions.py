import json
from dataclasses import dataclass
from sqlite3 import Connection, Row


@dataclass(frozen=True)
class SignRevision:
    id: str
    sign: str
    overrides: dict[str, str]


def create_sign_revision_tables(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS sign_revisions (
            number INTEGER PRIMARY KEY,
            id TEXT GENERATED ALWAYS AS ('sign-rev-' || number) STORED UNIQUE,
            sign TEXT NOT NULL REFERENCES signs(id),
            overrides_json TEXT NOT NULL,
            UNIQUE (sign, id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS sign_current (
            sign TEXT PRIMARY KEY REFERENCES signs(id),
            revision TEXT NOT NULL,
            FOREIGN KEY (sign, revision) REFERENCES sign_revisions(sign, id)
        )
    ''')


def append_revision(db: Connection, sign_id: str, overrides: dict[str, str]) -> SignRevision:
    number = db.execute(
        'INSERT INTO sign_revisions(sign, overrides_json) VALUES (?, ?)',
        (sign_id, json.dumps(overrides, ensure_ascii=False)),
    ).lastrowid
    row = db.execute('SELECT id FROM sign_revisions WHERE number = ?', (number,)).fetchone()
    revision_id = row['id']
    db.execute('''
        INSERT INTO sign_current(sign, revision) VALUES (?, ?)
        ON CONFLICT(sign) DO UPDATE SET revision = excluded.revision
    ''', (sign_id, revision_id))
    return SignRevision(revision_id, sign_id, overrides.copy())


def _decode(row: Row | None) -> SignRevision | None:
    if row is None:
        return None
    return SignRevision(row['id'], row['sign'], json.loads(row['overrides_json']))


def load_sign_revision(db: Connection, revision_id: str) -> SignRevision | None:
    row = db.execute(
        'SELECT id, sign, overrides_json FROM sign_revisions WHERE id = ?', (revision_id,)
    ).fetchone()
    return _decode(row)


def load_current_revision(db: Connection, sign_id: str) -> SignRevision | None:
    row = db.execute('''
        SELECT revision.id, revision.sign, revision.overrides_json
        FROM sign_current AS current
        JOIN sign_revisions AS revision ON revision.sign = current.sign
                                       AND revision.id = current.revision
        WHERE current.sign = ?
    ''', (sign_id,)).fetchone()
    return _decode(row)
