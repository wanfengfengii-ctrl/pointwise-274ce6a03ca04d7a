from sqlite3 import Connection

from signs.bindings import SignBinding, update_sign_template
from signs.revisions import append_revision
from signs.snapshots import SignSnapshot, load_current_sign_snapshot
from templates.publication import load_published_template, load_template_lineage


class UpgradeRejected(Exception):
    def __init__(
        self,
        status: int,
        message: str,
        *,
        retired_slots: tuple[str, ...] | list[str] | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.retired_slots = None if retired_slots is None else tuple(retired_slots)


def upgrade_sign(db: Connection, sign_id: str, payload: object) -> SignSnapshot:
    if not isinstance(payload, dict) or payload.keys() != {'target'}:
        raise UpgradeRejected(400, 'upgrade requires a target template')
    target_id = payload['target']
    if not isinstance(target_id, str) or not target_id:
        raise UpgradeRejected(400, 'target must be a formal template number')

    current = load_current_sign_snapshot(db, sign_id)
    target = load_published_template(db, target_id)
    if target is None:
        raise UpgradeRejected(404, 'unknown target template')

    current_template_id = current.revision.template or current.binding.template

    # Re-posting the target that is already current is an idempotent read of
    # the latest state, including edits made after the upgrade revision.
    if target.id == current_template_id:
        return current

    lineage = load_template_lineage(db, target.id)
    if lineage is None or lineage.base != current_template_id:
        raise UpgradeRejected(409, 'target must be a direct successor of the current template')

    inherited_old_keys = {
        predecessor
        for predecessor in lineage.sources.values()
        if predecessor is not None
    }
    retired_slots = [
        spec.key
        for spec in current.template.slots
        if spec.key in current.revision.overrides
        and spec.key not in inherited_old_keys
    ]
    if retired_slots:
        raise UpgradeRejected(
            409,
            'human-overridden slots lose their successor: ' + ', '.join(retired_slots),
            retired_slots=retired_slots,
        )

    upgraded_overrides: dict[str, str] = {}
    for spec in target.slots:
        predecessor = lineage.sources.get(spec.key)
        if predecessor is not None and predecessor in current.revision.overrides:
            upgraded_overrides[spec.key] = current.revision.overrides[predecessor]

    update_sign_template(db, current.binding.id, target.id)
    revision = append_revision(
        db, current.binding.id, upgraded_overrides, target.id
    )
    binding = SignBinding(current.binding.id, target.id, current.binding.assets)
    return SignSnapshot(binding, target, revision)
