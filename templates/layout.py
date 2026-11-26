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


def validate_layout(slots: object) -> tuple[SlotSpec, ...]:
    if not isinstance(slots, list) or not slots:
        raise InvalidLayout('slots must be a non-empty array')
    seen = set()
    layout = []
    for raw in slots:
        if not isinstance(raw, dict) or raw.keys() != {'key', 'label', 'default', 'width', 'max_lines'}:
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
