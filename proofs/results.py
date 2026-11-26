import json
from dataclasses import asdict, dataclass
from sqlite3 import Connection


@dataclass(frozen=True)
class ProofSlot:
    key: str
    label: str
    text: str
    overridden: bool
    lines: tuple[str, ...]
    overflow: bool


@dataclass(frozen=True)
class ProofRecord:
    proof: str
    sign: str
    revision: str
    template: str
    assets: tuple[str, ...]
    title: str
    slots: tuple[ProofSlot, ...]

    @property
    def overflow(self) -> tuple[str, ...]:
        return tuple(slot.key for slot in self.slots if slot.overflow)


def create_proof_tables(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS proofs (
            number INTEGER PRIMARY KEY,
            id TEXT GENERATED ALWAYS AS ('proof-' || number) STORED UNIQUE,
            sign TEXT NOT NULL,
            revision TEXT NOT NULL,
            template TEXT NOT NULL REFERENCES published_templates(id),
            assets_json TEXT NOT NULL,
            title TEXT NOT NULL,
            slots_json TEXT NOT NULL,
            FOREIGN KEY (sign, revision) REFERENCES sign_revisions(sign, id)
        )
    ''')


def save_proof(
    db: Connection,
    *,
    sign: str,
    revision: str,
    template: str,
    assets: tuple[str, ...],
    title: str,
    slots: tuple[ProofSlot, ...],
) -> ProofRecord:
    number = db.execute('''
        INSERT INTO proofs(sign, revision, template, assets_json, title, slots_json)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        sign, revision, template, json.dumps(assets), title,
        json.dumps([asdict(slot) for slot in slots], ensure_ascii=False),
    )).lastrowid
    row = db.execute('SELECT id FROM proofs WHERE number = ?', (number,)).fetchone()
    return ProofRecord(row['id'], sign, revision, template, assets, title, slots)


def load_proof(db: Connection, proof_id: str) -> ProofRecord | None:
    row = db.execute('''
        SELECT id, sign, revision, template, assets_json, title, slots_json
        FROM proofs WHERE id = ?
    ''', (proof_id,)).fetchone()
    if row is None:
        return None
    slots = []
    for data in json.loads(row['slots_json']):
        data['lines'] = tuple(data['lines'])
        slots.append(ProofSlot(**data))
    return ProofRecord(
        row['id'], row['sign'], row['revision'], row['template'],
        tuple(json.loads(row['assets_json'])), row['title'], tuple(slots),
    )
