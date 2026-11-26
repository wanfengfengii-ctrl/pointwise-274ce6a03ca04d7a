from dataclasses import dataclass
from sqlite3 import Connection

from assets.catalog import AssetRecord
from assets.validation import AssetContent


@dataclass(frozen=True)
class AssetRevision:
    id: str
    asset_id: str
    name: str
    kind: str
    body: str | None
    alt: str | None
    source: str


def create_asset_revision_tables(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS asset_revisions (
            number INTEGER PRIMARY KEY,
            id TEXT GENERATED ALWAYS AS ('asset-rev-' || number) STORED UNIQUE,
            asset TEXT NOT NULL REFERENCES asset_catalog(id),
            body TEXT,
            alt TEXT,
            source TEXT NOT NULL
        )
    ''')


def save_asset_revision(
    db: Connection, asset: AssetRecord, content: AssetContent
) -> AssetRevision:
    source = content.source if content.source is not None else asset.id
    number = db.execute(
        'INSERT INTO asset_revisions(asset, body, alt, source) VALUES (?, ?, ?, ?)',
        (asset.id, content.body, content.alt, source),
    ).lastrowid
    row = db.execute('SELECT id FROM asset_revisions WHERE number = ?', (number,)).fetchone()
    return AssetRevision(
        row['id'], asset.id, asset.name, asset.kind, content.body, content.alt, source
    )


def load_asset_revision(db: Connection, revision_id: str) -> AssetRevision | None:
    row = db.execute('''
        SELECT revision.id, revision.asset AS asset_id, catalog.name, catalog.kind,
               revision.body, revision.alt, revision.source
        FROM asset_revisions AS revision
        JOIN asset_catalog AS catalog ON catalog.id = revision.asset
        WHERE revision.id = ?
    ''', (revision_id,)).fetchone()
    return AssetRevision(**dict(row)) if row is not None else None
