import json
from dataclasses import dataclass
from sqlite3 import Connection, Row


@dataclass(frozen=True)
class SignRevision:
    id: str
    sign: str
    overrides: dict[str, str]
    template: str | None = None


def _has_column(db: Connection, table: str, column: str) -> bool:
    return any(row['name'] == column for row in db.execute(f'PRAGMA table_info({table})'))


def create_sign_revision_tables(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS sign_revisions (
            number INTEGER PRIMARY KEY,
            id TEXT GENERATED ALWAYS AS ('sign-rev-' || number) STORED UNIQUE,
            sign TEXT NOT NULL REFERENCES signs(id),
            overrides_json TEXT NOT NULL,
            template TEXT REFERENCES published_templates(id),
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

    # V1 databases had no per-revision template. Every pre-upgrade revision
    # used the template still recorded on its sign binding.
    if not _has_column(db, 'sign_revisions', 'template'):
        db.execute('ALTER TABLE sign_revisions ADD COLUMN template TEXT')
    db.execute('''
        UPDATE sign_revisions
        SET template = (
            SELECT signs.template
            FROM signs
            WHERE signs.id = sign_revisions.sign
        )
        WHERE template IS NULL
    ''')


def append_revision(
    db: Connection,
    sign_id: str,
    overrides: dict[str, str],
    template_id: str | None = None,
) -> SignRevision:
    if template_id is None:
        row = db.execute('SELECT template FROM signs WHERE id = ?', (sign_id,)).fetchone()
        if row is None:
            raise ValueError(f'unknown sign: {sign_id}')
        template_id = row['template']

    number = db.execute(
        'INSERT INTO sign_revisions(sign, overrides_json, template) VALUES (?, ?, ?)',
        (sign_id, json.dumps(overrides, ensure_ascii=False), template_id),
    ).lastrowid
    row = db.execute('SELECT id FROM sign_revisions WHERE number = ?', (number,)).fetchone()
    revision_id = row['id']
    db.execute('''
        INSERT INTO sign_current(sign, revision) VALUES (?, ?)
        ON CONFLICT(sign) DO UPDATE SET revision = excluded.revision
    ''', (sign_id, revision_id))
    return SignRevision(revision_id, sign_id, overrides.copy(), template_id)


def _decode(row: Row | None) -> SignRevision | None:
    if row is None:
        return None
    keys = row.keys()
    template = row['template'] if 'template' in keys else None
    return SignRevision(row['id'], row['sign'], json.loads(row['overrides_json']), template)


def load_sign_revision(db: Connection, revision_id: str) -> SignRevision | None:
    row = db.execute(
        'SELECT id, sign, overrides_json, template FROM sign_revisions WHERE id = ?',
        (revision_id,),
    ).fetchone()
    return _decode(row)


def load_current_revision(db: Connection, sign_id: str) -> SignRevision | None:
    row = db.execute('''
        SELECT revision.id, revision.sign, revision.overrides_json, revision.template
        FROM sign_current AS current
        JOIN sign_revisions AS revision ON revision.sign = current.sign
                                       AND revision.id = current.revision
        WHERE current.sign = ?
    ''', (sign_id,)).fetchone()
    return _decode(row)
