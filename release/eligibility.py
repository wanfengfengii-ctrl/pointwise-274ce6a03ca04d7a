from dataclasses import dataclass
from sqlite3 import Connection, IntegrityError

from proofs.results import ProofRecord, load_proof
from signs.bindings import load_sign_binding
from signs.revisions import load_current_revision


class ReleaseRejected(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class EligibleProof:
    proof: ProofRecord


def check_eligibility(db: Connection, sign_id: str, proof_id: str) -> EligibleProof:
    binding = load_sign_binding(db, sign_id)
    if binding is None:
        raise ReleaseRejected(404, 'unknown sign')
    proof = load_proof(db, proof_id)
    if proof is None:
        raise ReleaseRejected(404, 'unknown proof')
    if proof.sign != binding.id:
        raise ReleaseRejected(409, 'proof belongs to another sign')
    current = load_current_revision(db, binding.id)
    if current is None:
        raise IntegrityError('sign has no current revision')
    if proof.revision != current.id:
        raise ReleaseRejected(409, 'proof is for a historical revision')
    if proof.overflow:
        raise ReleaseRejected(409, 'proof has overflowing slots')
    return EligibleProof(proof)
