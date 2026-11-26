from sqlite3 import Connection

from templates.drafts import insert_draft, load_draft
from templates.layout import InvalidLayout, validate_revision_layout
from templates.publication import (
    PublishedTemplate,
    find_publication_by_draft,
    freeze_template,
    load_published_template,
    save_template_lineage,
)


class PublicationRejected(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def approve_and_publish(db: Connection, draft_id: str) -> PublishedTemplate:
    draft = load_draft(db, draft_id)
    if draft is None:
        raise PublicationRejected(404, 'unknown template draft')
    if find_publication_by_draft(db, draft_id) is not None:
        raise PublicationRejected(409, 'template draft already published')
    return freeze_template(db, draft)


def publish_template_revision(
    db: Connection, base_id: str, payload: object
) -> tuple[PublishedTemplate, dict[str, str | None]]:
    if not isinstance(payload, dict) or payload.keys() != {'title', 'slots'}:
        raise InvalidLayout('a template revision requires a string title and slots')
    if not isinstance(payload['title'], str):
        raise InvalidLayout('template revision title must be a string')

    base = load_published_template(db, base_id)
    if base is None:
        raise PublicationRejected(404, 'unknown published base template')

    slots, sources = validate_revision_layout(payload['slots'], base.slots)

    # The existing publication table freezes an approved draft. Store the
    # directly requested revision as its draft record as well, all in the
    # caller's write transaction.
    draft = insert_draft(db, payload['title'], slots)
    template = freeze_template(db, draft)
    save_template_lineage(db, template.id, base.id, sources)
    return template, sources
