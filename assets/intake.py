from sqlite3 import Connection

from assets.catalog import insert_asset_record
from assets.revisions import AssetRevision, save_asset_revision
from assets.validation import validate_asset


def freeze_asset(db: Connection, payload: dict) -> AssetRevision:
    content = validate_asset(payload)
    asset = insert_asset_record(db, content.name, content.kind)
    return save_asset_revision(db, asset, content)
