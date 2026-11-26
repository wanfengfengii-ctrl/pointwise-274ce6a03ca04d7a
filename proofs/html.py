from html import escape

from proofs.results import ProofRecord


def _literal(text: str) -> str:
    return escape(text).replace('\r', '&#13;')


def render_proof_html(proof: ProofRecord) -> bytes:
    title = _literal(proof.title)
    parts = [
        '<!doctype html>',
        '<html lang="zh-CN">',
        '<head>',
        '<meta charset="utf-8">',
        f'<title>{title}</title>',
        '<style>.line{white-space:pre;min-height:1em}h1,h2{white-space:pre-wrap}</style>',
        '</head>',
        '<body>',
        f'<h1>{title}</h1>',
        '<main>',
    ]
    for slot in proof.slots:
        parts.append(f'<section data-slot="{_literal(slot.key)}">')
        parts.append(f'<h2>{_literal(slot.label)}</h2>')
        for line in slot.lines:
            parts.append(f'<div class="line">{_literal(line)}</div>')
        parts.append('</section>')
    parts.extend(['</main>', '</body>', '</html>'])
    return ('\n'.join(parts) + '\n').encode('utf-8')
