from dataclasses import dataclass
from sqlite3 import Connection


@dataclass(frozen=True)
class AssetRecord:
    id: str
    name: str
    kind: str


def create_asset_catalog_tables(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS asset_catalog (
            number INTEGER PRIMARY KEY,
            id TEXT GENERATED ALWAYS AS ('asset-' || number) STORED UNIQUE,
            name TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('text', 'image'))
        )
    ''')


def insert_asset_record(db: Connection, name: str, kind: str) -> AssetRecord:
    number = db.execute(
        'INSERT INTO asset_catalog(name, kind) VALUES (?, ?)', (name, kind)
    ).lastrowid
    row = db.execute('SELECT id FROM asset_catalog WHERE number = ?', (number,)).fetchone()
    return AssetRecord(row['id'], name, kind)
