import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.support import Client, running_service, two_slots


def expect(client: Client, status: int, path: str, payload=None) -> dict:
    reply = client.request(path, payload)
    if reply.status != status:
        raise AssertionError(f'{path}: expected {status}, got {reply.status} {reply.body}')
    return reply.body


def equal(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f'expected {expected!r}, got {actual!r}')


def edit(client: Client, sign: str, key: str, op: str, **fields) -> dict:
    return expect(client, 200, f'/signs/{sign}/edits', {'key': key, 'op': op, **fields})


def main() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'riverside.sqlite3'
        with running_service(path) as client:
            text = expect(client, 201, '/assets', {
                'name': '渡口说明', 'kind': 'text', 'body': '渡口曾连接两岸村落。', 'source': '馆档-017',
            })
            photo = expect(client, 201, '/assets', {
                'name': '桥景照片', 'kind': 'image', 'alt': '木桥跨过旧渡口。', 'source': '馆档-023',
            })
            assets = [text['revision'], photo['revision']]
            draft = expect(client, 201, '/templates/drafts', {'title': '河岸记忆', 'slots': two_slots()})
            template = expect(client, 201, f"/templates/drafts/{draft['draft']}/publish", {})
            sign = expect(client, 201, '/signs', {'template': template['template'], 'assets': assets})['sign']
            edit(client, sign, 'A', 'write', text='河岸')
            blank = edit(client, sign, 'B', 'write', text='')
            proof_path = f'/signs/{sign}/proofs'
            blank_proof = expect(client, 201, proof_path, {'revision': blank['revision']})
            equal([slot['overridden'] for slot in blank_proof['slots']], [True, True])
            equal([slot['lines'] for slot in blank_proof['slots']], [['河岸'], []])

            ready = edit(client, sign, 'B', 'reset')
            proof = expect(client, 201, proof_path, {'revision': ready['revision']})
            equal([slot['key'] for slot in proof['slots']], ['A', 'B'])
            equal([slot['lines'] for slot in proof['slots']], [['河岸'], ['木桥']])
            equal([slot['overridden'] for slot in proof['slots']], [True, False])
            releases = f'/signs/{sign}/releases'
            issued = expect(client, 201, releases, {'proof': proof['proof']})
            receipt_path = f"/releases/{issued['release']}"
            fixed = expect(client, 200, receipt_path)
            equal(fixed['source'], {
                'proof': proof['proof'], 'sign': sign, 'revision': ready['revision'],
                'template': template['template'], 'assets': assets,
            })
            if '<div class="line">木桥</div>' not in fixed['html']:
                raise AssertionError('receipt lost the reviewed B line')

            long = edit(client, sign, 'A', 'write', text='甲乙丙丁戊')
            long_proof = expect(client, 201, proof_path, {'revision': long['revision']})
            equal(long_proof['slots'][0]['lines'], ['甲乙', '丙丁', '戊'])
            equal(long_proof['overflow'], ['A'])
            refused = client.request(releases, {'proof': long_proof['proof']})
            equal(refused.status, 409)
            equal(expect(client, 200, f"/proofs/{proof['proof']}"), proof)

        with running_service(path) as reopened:
            reclaimed = expect(reopened, 200, receipt_path)
            equal(reclaimed, fixed)
            equal(reclaimed['html'].encode('utf-8'), fixed['html'].encode('utf-8'))
            equal(expect(reopened, 200, f'/signs/{sign}')['revision'], long['revision'])
        print(json.dumps({
            '展签': sign,
            '人工留空校样': blank_proof['slots'][1]['lines'],
            '发阅栏文': [slot['lines'] for slot in proof['slots']],
            '后续校样栏文': long_proof['slots'][0]['lines'],
            '拒绝发阅状态': refused.status,
            '旧发阅号': reclaimed['release'],
            '重开复领来源': reclaimed['source'],
        }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
