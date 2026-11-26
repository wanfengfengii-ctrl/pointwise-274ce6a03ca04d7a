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


@dataclass(frozen=True)
class TemplateLineage:
    child: str
    base: str
    sources: dict[str, str | None]


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
    db.execute('''
        CREATE TABLE IF NOT EXISTS template_lineage (
            child TEXT PRIMARY KEY REFERENCES published_templates(id),
            base TEXT NOT NULL REFERENCES published_templates(id),
            mapping_json TEXT NOT NULL
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


def save_template_lineage(
    db: Connection, child: str, base: str, sources: dict[str, str | None]
) -> TemplateLineage:
    db.execute('''
        INSERT INTO template_lineage(child, base, mapping_json)
        VALUES (?, ?, ?)
    ''', (child, base, json.dumps(sources, ensure_ascii=False)))
    return TemplateLineage(child, base, sources.copy())


def load_template_lineage(db: Connection, child: str) -> TemplateLineage | None:
    row = db.execute('''
        SELECT child, base, mapping_json
        FROM template_lineage
        WHERE child = ?
    ''', (child,)).fetchone()
    if row is None:
        return None
    return TemplateLineage(
        row['child'], row['base'], json.loads(row['mapping_json'])
    )
