import json
from dataclasses import asdict, dataclass
from sqlite3 import Connection, Row

from templates.drafts import TemplateDraft
from templates.layout import SlotSpec


@dataclass(frozen=True)
class PublishedTemplate:
    id: str
    draft: str
    title: str
    slots: tuple[SlotSpec, ...]


def create_template_release_tables(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS published_templates (
            number INTEGER PRIMARY KEY,
            id TEXT GENERATED ALWAYS AS ('template-' || number) STORED UNIQUE,
            draft TEXT NOT NULL UNIQUE REFERENCES template_drafts(id),
            title TEXT NOT NULL,
            slots_json TEXT NOT NULL
        )
    ''')


def freeze_template(db: Connection, draft: TemplateDraft) -> PublishedTemplate:
    number = db.execute(
        'INSERT INTO published_templates(draft, title, slots_json) VALUES (?, ?, ?)',
        (draft.id, draft.title, json.dumps([asdict(slot) for slot in draft.slots], ensure_ascii=False)),
    ).lastrowid
    row = db.execute('SELECT id FROM published_templates WHERE number = ?', (number,)).fetchone()
    return PublishedTemplate(row['id'], draft.id, draft.title, draft.slots)


def _decode(row: Row | None) -> PublishedTemplate | None:
    if row is None:
        return None
    slots = tuple(SlotSpec(**item) for item in json.loads(row['slots_json']))
    return PublishedTemplate(row['id'], row['draft'], row['title'], slots)


def load_published_template(db: Connection, template_id: str) -> PublishedTemplate | None:
    row = db.execute(
        'SELECT id, draft, title, slots_json FROM published_templates WHERE id = ?',
        (template_id,),
    ).fetchone()
    return _decode(row)


def find_publication_by_draft(db: Connection, draft_id: str) -> PublishedTemplate | None:
    row = db.execute(
        'SELECT id, draft, title, slots_json FROM published_templates WHERE draft = ?',
        (draft_id,),
    ).fetchone()
    return _decode(row)
