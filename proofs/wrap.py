from dataclasses import dataclass


@dataclass(frozen=True)
class WrappedSlot:
    lines: tuple[str, ...]
    overflow: bool


def wrap_text(text: str, width: int) -> tuple[str, ...]:
    if type(width) is not int or width <= 0:
        raise ValueError('width must be a positive integer')
    if text == '':
        return ()
    lines = []
    for segment in text.split('\n'):
        if segment == '':
            lines.append('')
        else:
            for offset in range(0, len(segment), width):
                lines.append(segment[offset:offset + width])
    return tuple(lines)


def measure_slot(text: str, width: int, max_lines: int) -> WrappedSlot:
    if type(max_lines) is not int or max_lines <= 0:
        raise ValueError('max_lines must be a positive integer')
    lines = wrap_text(text, width)
    return WrappedSlot(lines, len(lines) > max_lines)
