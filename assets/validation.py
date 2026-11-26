from dataclasses import dataclass


class InvalidAsset(ValueError):
    pass


@dataclass(frozen=True)
class AssetContent:
    name: str
    kind: str
    body: str | None
    alt: str | None
    source: str | None


def _optional_string(payload: dict, key: str) -> str | None:
    if key not in payload:
        return None
    value = payload[key]
    if not isinstance(value, str):
        raise InvalidAsset(f'{key} must be a string')
    return value


def validate_asset(payload: dict) -> AssetContent:
    if payload.keys() - {'name', 'kind', 'body', 'alt', 'source'}:
        raise InvalidAsset('unexpected asset field')
    name = payload.get('name')
    if not isinstance(name, str) or not name.strip():
        raise InvalidAsset('name must be non-blank')
    kind = payload.get('kind')
    if kind not in ('text', 'image'):
        raise InvalidAsset('kind must be text or image')

    body = _optional_string(payload, 'body')
    alt = _optional_string(payload, 'alt')
    source = _optional_string(payload, 'source')
    if kind == 'text' and (body is None or not body.strip()):
        raise InvalidAsset('text assets require body')
    if kind == 'image' and (alt is None or not alt.strip()):
        raise InvalidAsset('image assets require alt')
    if source is not None and not source.strip():
        raise InvalidAsset('source must be non-blank when provided')
    return AssetContent(name, kind, body, alt, source)
