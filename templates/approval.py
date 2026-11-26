from sqlite3 import Connection

from templates.drafts import load_draft
from templates.publication import PublishedTemplate, find_publication_by_draft, freeze_template


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
