import json
from sqlite3 import Connection

from release.issue import IssuedRelease
from release.packaging import ReleasePackage, ReleaseSource


class ReleaseNotFound(LookupError):
    status = 404


def get_release(db: Connection, release_id: str) -> IssuedRelease:
    row = db.execute('''
        SELECT id, proof, html, source_json FROM releases WHERE id = ?
    ''', (release_id,)).fetchone()
    if row is None:
        raise ReleaseNotFound('unknown release')
    source = json.loads(row['source_json'])
    source['assets'] = tuple(source['assets'])
    package = ReleasePackage(row['html'], ReleaseSource(proof=row['proof'], **source))
    return IssuedRelease(row['id'], package)
