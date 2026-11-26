from sqlite3 import Connection

from proofs.resolve import resolve_proof_input
from proofs.results import ProofRecord, ProofSlot, save_proof
from proofs.wrap import measure_slot


def make_proof(db: Connection, sign_id: str, revision_id: str) -> ProofRecord:
    source = resolve_proof_input(db, sign_id, revision_id)
    slots = []
    for slot in source.slots:
        wrapped = measure_slot(slot.text, slot.width, slot.max_lines)
        slots.append(ProofSlot(
            slot.key, slot.label, slot.text, slot.overridden, wrapped.lines, wrapped.overflow
        ))
    return save_proof(
        db,
        sign=source.sign,
        revision=source.revision,
        template=source.template,
        assets=source.assets,
        title=source.title,
        slots=tuple(slots),
    )
