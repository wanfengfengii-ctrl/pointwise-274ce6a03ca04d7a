from dataclasses import dataclass

from templates.layout import SlotSpec


class EditRejected(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class SlotEdit:
    key: str
    op: str
    text: str | None


def validate_edit(payload: dict) -> SlotEdit:
    key = payload.get('key')
    if not isinstance(key, str) or not key:
        raise EditRejected(400, 'key must be a non-empty string')
    operation = payload.get('op')
    if operation == 'write':
        if payload.keys() != {'key', 'op', 'text'} or not isinstance(payload.get('text'), str):
            raise EditRejected(400, 'write requires a string text')
        return SlotEdit(key, operation, payload['text'])
    if operation == 'reset' and payload.keys() == {'key', 'op'}:
        return SlotEdit(key, operation, None)
    raise EditRejected(400, 'expected write or reset with the corresponding fields')


def apply_edit(overrides: dict[str, str], edit: SlotEdit) -> dict[str, str]:
    updated = overrides.copy()
    if edit.op == 'reset':
        updated.pop(edit.key, None)
    else:
        if edit.text is None:
            raise ValueError('a write edit requires text')
        updated[edit.key] = edit.text
    return updated


def effective_slot(slot: SlotSpec, overrides: dict[str, str]) -> tuple[str, bool]:
    if slot.key in overrides:
        return overrides[slot.key], True
    return slot.default, False
