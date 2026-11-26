from dataclasses import dataclass


class InvalidLayout(ValueError):
    pass


@dataclass(frozen=True)
class SlotSpec:
    key: str
    label: str
    default: str
    width: int
    max_lines: int


SLOT_FIELDS = {'key', 'label', 'default', 'width', 'max_lines'}
REVISION_SLOT_FIELDS = SLOT_FIELDS | {'from'}


def validate_layout(slots: object) -> tuple[SlotSpec, ...]:
    if not isinstance(slots, list) or not slots:
        raise InvalidLayout('slots must be a non-empty array')
    seen = set()
    layout = []
    for raw in slots:
        if not isinstance(raw, dict) or raw.keys() != SLOT_FIELDS:
            raise InvalidLayout('each slot requires key, label, default, width and max_lines')
        key = raw['key']
        if not isinstance(key, str) or not key:
            raise InvalidLayout('slot key must be a non-empty string')
        if key in seen:
            raise InvalidLayout(f'duplicate slot key: {key}')
        if not isinstance(raw['label'], str) or not isinstance(raw['default'], str):
            raise InvalidLayout('slot label and default must be strings')
        for limit in ('width', 'max_lines'):
            if type(raw[limit]) is not int or raw[limit] <= 0:
                raise InvalidLayout(f'{limit} must be a positive integer')
        seen.add(key)
        layout.append(SlotSpec(**raw))
    return tuple(layout)


def validate_revision_layout(
    slots: object, base_slots: tuple[SlotSpec, ...]
) -> tuple[tuple[SlotSpec, ...], dict[str, str | None]]:
    if not isinstance(slots, list) or not slots:
        raise InvalidLayout('slots must be a non-empty array')

    base_keys = {slot.key for slot in base_slots}
    normal_slots = []
    for raw in slots:
        if not isinstance(raw, dict) or raw.keys() != REVISION_SLOT_FIELDS:
            raise InvalidLayout(
                'each revision slot requires key, label, default, width, max_lines and from'
            )
        normal_slots.append({field: raw[field] for field in SLOT_FIELDS})

    layout = validate_layout(normal_slots)
    sources: dict[str, str | None] = {}
    inherited = set()
    for spec, raw in zip(layout, slots, strict=True):
        predecessor = raw['from']
        if predecessor is not None:
            if not isinstance(predecessor, str) or not predecessor:
                raise InvalidLayout('from must be a base slot key or null')
            if predecessor not in base_keys:
                raise InvalidLayout(f'unknown base slot in from: {predecessor}')
            if predecessor in inherited:
                raise InvalidLayout(f'base slot is inherited more than once: {predecessor}')
            inherited.add(predecessor)
        sources[spec.key] = predecessor

    return layout, sources
