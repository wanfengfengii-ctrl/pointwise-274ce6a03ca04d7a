from dataclasses import dataclass
from sqlite3 import Connection

from assets.revisions import load_asset_revision
from templates.drafts import load_draft
from templates.publication import PublishedTemplate, load_published_template


class BindingRejected(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class SignBinding:
    id: str
    template: str
    assets: tuple[str, ...]


def create_sign_binding_tables(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS signs (
            number INTEGER PRIMARY KEY,
            id TEXT GENERATED ALWAYS AS ('sign-' || number) STORED UNIQUE,
            template TEXT NOT NULL REFERENCES published_templates(id)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS sign_assets (
            sign TEXT NOT NULL REFERENCES signs(id),
            position INTEGER NOT NULL,
            asset_revision TEXT NOT NULL REFERENCES asset_revisions(id),
            PRIMARY KEY (sign, position)
        )
    ''')


def resolve_binding(
    db: Connection, template_id: str, assets: tuple[str, ...]
) -> PublishedTemplate:
    template = load_published_template(db, template_id)
    if template is None:
        if load_draft(db, template_id) is not None:
            raise BindingRejected(409, 'a published template number is required')
        raise BindingRejected(404, 'unknown template')
    for revision in assets:
        if load_asset_revision(db, revision) is None:
            raise BindingRejected(404, f'unknown asset revision: {revision}')
    return template


def insert_sign_binding(db: Connection, template: str, assets: tuple[str, ...]) -> SignBinding:
    number = db.execute('INSERT INTO signs(template) VALUES (?)', (template,)).lastrowid
    row = db.execute('SELECT id FROM signs WHERE number = ?', (number,)).fetchone()
    sign_id = row['id']
    db.executemany(
        'INSERT INTO sign_assets(sign, position, asset_revision) VALUES (?, ?, ?)',
        ((sign_id, position, revision) for position, revision in enumerate(assets)),
    )
    return SignBinding(sign_id, template, assets)


def load_sign_binding(db: Connection, sign_id: str) -> SignBinding | None:
    row = db.execute('SELECT id, template FROM signs WHERE id = ?', (sign_id,)).fetchone()
    if row is None:
        return None
    revisions = db.execute('''
        SELECT asset_revision FROM sign_assets WHERE sign = ? ORDER BY position
    ''', (sign_id,))
    return SignBinding(row['id'], row['template'], tuple(item[0] for item in revisions))
