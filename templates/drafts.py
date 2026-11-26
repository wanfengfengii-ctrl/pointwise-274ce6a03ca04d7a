import json
from dataclasses import asdict, dataclass
from sqlite3 import Connection

from templates.layout import InvalidLayout, SlotSpec, validate_layout


@dataclass(frozen=True)
class TemplateDraft:
    id: str
    title: str
    slots: tuple[SlotSpec, ...]


def create_draft_tables(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS template_drafts (
            number INTEGER PRIMARY KEY,
            id TEXT GENERATED ALWAYS AS ('draft-' || number) STORED UNIQUE,
            title TEXT NOT NULL,
            slots_json TEXT NOT NULL
        )
    ''')


def create_draft(db: Connection, payload: dict) -> TemplateDraft:
    if payload.keys() != {'title', 'slots'} or not isinstance(payload['title'], str):
        raise InvalidLayout('a template draft requires a string title and slots')
    slots = validate_layout(payload['slots'])
    title = payload['title']
    number = db.execute(
        'INSERT INTO template_drafts(title, slots_json) VALUES (?, ?)',
        (title, json.dumps([asdict(slot) for slot in slots], ensure_ascii=False)),
    ).lastrowid
    row = db.execute('SELECT id FROM template_drafts WHERE number = ?', (number,)).fetchone()
    return TemplateDraft(row['id'], title, slots)


def load_draft(db: Connection, draft_id: str) -> TemplateDraft | None:
    row = db.execute(
        'SELECT id, title, slots_json FROM template_drafts WHERE id = ?', (draft_id,)
    ).fetchone()
    if row is None:
        return None
    slots = tuple(SlotSpec(**item) for item in json.loads(row['slots_json']))
    return TemplateDraft(row['id'], row['title'], slots)
