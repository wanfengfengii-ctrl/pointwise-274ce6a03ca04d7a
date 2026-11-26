import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from os import PathLike

from assets.catalog import create_asset_catalog_tables
from assets.revisions import create_asset_revision_tables
from proofs.results import create_proof_tables
from release.issue import create_release_tables
from signs.bindings import create_sign_binding_tables
from signs.revisions import create_sign_revision_tables
from templates.drafts import create_draft_tables
from templates.publication import create_template_release_tables


def open_database(path: str | PathLike[str]) -> sqlite3.Connection:
    db = sqlite3.connect(path, isolation_level=None, timeout=5.0)
    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
    except BaseException:
        db.close()
        raise
    return db


@contextmanager
def write_transaction(db: sqlite3.Connection) -> Iterator[None]:
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except BaseException:
        db.rollback()
        raise


def initialize_database(path: str | PathLike[str]) -> None:
    with closing(open_database(path)) as db, write_transaction(db):
        create_asset_catalog_tables(db)
        create_asset_revision_tables(db)
        create_draft_tables(db)
        create_template_release_tables(db)
        create_sign_binding_tables(db)
        create_sign_revision_tables(db)
        create_proof_tables(db)
        create_release_tables(db)
