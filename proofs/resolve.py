from dataclasses import dataclass
from sqlite3 import Connection

from signs.overrides import effective_slot
from signs.snapshots import load_sign_snapshot


@dataclass(frozen=True)
class ResolvedSlot:
    key: str
    label: str
    text: str
    overridden: bool
    width: int
    max_lines: int


@dataclass(frozen=True)
class ProofInput:
    sign: str
    revision: str
    template: str
    assets: tuple[str, ...]
    title: str
    slots: tuple[ResolvedSlot, ...]


def resolve_proof_input(db: Connection, sign_id: str, revision_id: str) -> ProofInput:
    snapshot = load_sign_snapshot(db, sign_id, revision_id)
    slots = []
    for spec in snapshot.template.slots:
        text, overridden = effective_slot(spec, snapshot.revision.overrides)
        slots.append(ResolvedSlot(spec.key, spec.label, text, overridden, spec.width, spec.max_lines))
    return ProofInput(
        snapshot.binding.id,
        snapshot.revision.id,
        snapshot.template.id,
        snapshot.binding.assets,
        snapshot.template.title,
        tuple(slots),
    )
