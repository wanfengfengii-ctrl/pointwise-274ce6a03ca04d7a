import json
from dataclasses import asdict, dataclass
from sqlite3 import Connection

from release.eligibility import check_eligibility
from release.packaging import ReleasePackage, package_release


@dataclass(frozen=True)
class IssuedRelease:
    id: str
    package: ReleasePackage


def create_release_tables(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS releases (
            number INTEGER PRIMARY KEY,
            id TEXT GENERATED ALWAYS AS ('release-' || number) STORED UNIQUE,
            proof TEXT NOT NULL REFERENCES proofs(id),
            html BLOB NOT NULL,
            source_json TEXT NOT NULL
        )
    ''')


def issue_release(db: Connection, sign_id: str, proof_id: str) -> IssuedRelease:
    package = package_release(check_eligibility(db, sign_id, proof_id))
    source = asdict(package.source)
    proof = source.pop('proof')
    number = db.execute('''
        INSERT INTO releases(proof, html, source_json) VALUES (?, ?, ?)
    ''', (proof, package.html, json.dumps(source))).lastrowid
    row = db.execute('SELECT id FROM releases WHERE number = ?', (number,)).fetchone()
    return IssuedRelease(row['id'], package)
