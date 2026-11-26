from sqlite3 import Connection

from signs.bindings import insert_sign_binding, resolve_binding
from signs.overrides import EditRejected, apply_edit, validate_edit
from signs.revisions import append_revision
from signs.snapshots import SignSnapshot, load_current_sign_snapshot


def create_sign(db: Connection, template_id: str, assets: tuple[str, ...]) -> SignSnapshot:
    template = resolve_binding(db, template_id, assets)
    binding = insert_sign_binding(db, template.id, assets)
    revision = append_revision(db, binding.id, {}, template.id)
    return SignSnapshot(binding, template, revision)


def edit_sign(db: Connection, sign_id: str, payload: dict) -> SignSnapshot:
    edit = validate_edit(payload)
    snapshot = load_current_sign_snapshot(db, sign_id)
    if all(slot.key != edit.key for slot in snapshot.template.slots):
        raise EditRejected(404, 'unknown slot for this sign')
    overrides = apply_edit(snapshot.revision.overrides, edit)
    revision = append_revision(db, sign_id, overrides, snapshot.template.id)
    return SignSnapshot(snapshot.binding, snapshot.template, revision)
