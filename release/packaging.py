from dataclasses import dataclass

from proofs.html import render_proof_html
from release.eligibility import EligibleProof


@dataclass(frozen=True)
class ReleaseSource:
    proof: str
    sign: str
    revision: str
    template: str
    assets: tuple[str, ...]


@dataclass(frozen=True)
class ReleasePackage:
    html: bytes
    source: ReleaseSource


def package_release(eligible: EligibleProof) -> ReleasePackage:
    proof = eligible.proof
    source = ReleaseSource(proof.proof, proof.sign, proof.revision, proof.template, proof.assets)
    return ReleasePackage(render_proof_html(proof), source)
