from dataclasses import dataclass
from sqlite3 import Connection, IntegrityError

from signs.bindings import SignBinding, load_sign_binding
from signs.revisions import SignRevision, load_current_revision, load_sign_revision
from templates.publication import PublishedTemplate, load_published_template


class SignSnapshotRejected(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class SignSnapshot:
    binding: SignBinding
    template: PublishedTemplate
    revision: SignRevision


def _require_binding(db: Connection, sign_id: str) -> SignBinding:
    binding = load_sign_binding(db, sign_id)
    if binding is None:
        raise SignSnapshotRejected(404, 'unknown sign')
    return binding


def _snapshot(db: Connection, binding: SignBinding, revision: SignRevision) -> SignSnapshot:
    template = load_published_template(db, binding.template)
    if template is None:
        raise IntegrityError('sign has no published template')
    return SignSnapshot(binding, template, revision)


def load_sign_snapshot(db: Connection, sign_id: str, revision_id: str) -> SignSnapshot:
    binding = _require_binding(db, sign_id)
    revision = load_sign_revision(db, revision_id)
    if revision is None:
        raise SignSnapshotRejected(404, 'unknown sign revision')
    if revision.sign != binding.id:
        raise SignSnapshotRejected(409, 'revision belongs to another sign')
    return _snapshot(db, binding, revision)


def load_current_sign_snapshot(db: Connection, sign_id: str) -> SignSnapshot:
    binding = _require_binding(db, sign_id)
    revision = load_current_revision(db, sign_id)
    if revision is None:
        raise IntegrityError('sign has no current revision')
    return _snapshot(db, binding, revision)
