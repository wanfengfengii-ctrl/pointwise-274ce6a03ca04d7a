from tests.support import HTTPCase, scenario, two_slots


def _values(state):
    return [[item['key'], item['text'], item['overridden']] for item in state['slots']]


class CompositionTests(HTTPCase):
    def test_override_reset(self):
        sign = self.sign()
        self.assertEqual(_values(sign), [['A', '河岸', False], ['B', '木桥', False]])
        first = self.edit(sign, 'A', 'write', text='河岸')
        self.assertEqual(_values(first), [['A', '河岸', True], ['B', '木桥', False]])
        second = self.edit(first, 'B', 'write', text='')
        expected = [['A', '河岸', True], ['B', '', True]]
        self.assertEqual(_values(second), expected)
        proof = self.proof(second)
        self.assertEqual(proof['revision'], second['revision'])
        self.assertEqual(_values(proof), expected)
        proof_lines = [slot['lines'] for slot in proof['slots']]
        self.assertEqual(proof_lines, [['河岸'], []])
        self.assertEqual(proof['overflow'], [])
        reset_a = self.edit(second, 'A', 'reset')
        self.assertEqual(_values(reset_a), [['A', '河岸', False], ['B', '', True]])
        reset_b = self.edit(reset_a, 'B', 'reset')
        self.assertEqual(_values(reset_b), [['A', '河岸', False], ['B', '木桥', False]])
        states = (sign, first, second, reset_a, reset_b)
        self.assertEqual(len({state['revision'] for state in states}), len(states))
        scenario(
            'v4', {'defaults': {'A': '河岸', 'B': '木桥'}, 'writes': {'A': '河岸', 'B': ''}},
            expected, _values(second), [['河岸'], []], proof_lines,
            ['signs/overrides.py', 'signs/revisions.py', 'proofs/resolve.py', 'proofs/wrap.py'],
            '两次人工写入均存在。河岸占一行，空文占零行。',
        )

    def test_binding_errors(self):
        draft = self.api('/templates/drafts', {'title': '双栏', 'slots': two_slots()}, status=201)
        self.api('/signs', {'template': 'template-missing', 'assets': []}, status=404)
        self.api('/signs', {'template': draft['draft'], 'assets': []}, status=409)
        template = self.api(f"/templates/drafts/{draft['draft']}/publish", {}, status=201)
        asset = self.api('/assets', {'name': '图', 'kind': 'image', 'alt': '桥'}, status=201)
        for unknown in ('asset-rev-missing', asset['asset']):
            with self.subTest(unknown=unknown):
                self.api('/signs', {
                    'template': template['template'], 'assets': [asset['revision'], unknown],
                }, status=404)
        self.assertEqual(self.count('signs'), 0)
        self.assertEqual(self.count('sign_assets'), 0)
        self.assertEqual(self.count('sign_revisions'), 0)

    def test_fixed_binding(self):
        asset = self.api('/assets', {'name': '渡口', 'kind': 'text', 'body': '原文'}, status=201)
        original = self.publish()
        sign = self.sign(original['template'], [asset['revision']])
        slots = two_slots()
        slots[0]['default'] = '河畔'
        slots[1]['default'] = '石桥'
        independent = self.publish(list(reversed(slots)), title='另一站')
        other = self.sign(independent['template'])
        self.assertEqual(_values(other), [['B', '石桥', False], ['A', '河畔', False]])
        edited = self.edit(sign, 'A', 'write', text='现场')
        restored = self.edit(edited, 'A', 'reset')
        self.assertEqual(restored['template'], original['template'])
        self.assertEqual(restored['assets'], [asset['revision']])
        self.assertEqual(_values(restored), [['A', '河岸', False], ['B', '木桥', False]])
        proof = self.proof(restored)
        self.assertEqual(proof['template'], original['template'])
        self.assertEqual(_values(proof), _values(restored))

    def test_edit_errors(self):
        sign = self.sign()
        path = f"/signs/{sign['sign']}/edits"
        for bad in (
            {'key': 'A', 'op': 'append', 'text': '河岸'},
            {'key': 'A', 'op': 'write'},
            {'key': 'A', 'op': 'write', 'text': 9},
            {'key': 'B', 'op': 'reset', 'text': ''},
        ):
            with self.subTest(bad=bad):
                self.api(path, bad, status=400)
        self.api(path, {'key': 'C', 'op': 'reset'}, status=404)
        self.api('/signs/sign-missing/edits', {'key': 'A', 'op': 'reset'}, status=404)
        self.assertEqual(self.count('sign_revisions'), 1)
        self.assertEqual(self.api(f"/signs/{sign['sign']}"), sign)

    def test_historical_proof(self):
        sign = self.sign()
        blank = self.edit(sign, 'B', 'write', text='')
        restored = self.edit(blank, 'B', 'reset')
        old = self.proof(blank)
        new = self.proof(restored)
        self.assertNotEqual(old['proof'], new['proof'])
        self.assertEqual(old['revision'], blank['revision'])
        self.assertEqual(new['revision'], restored['revision'])
        self.assertEqual(_values(old), [['A', '河岸', False], ['B', '', True]])
        self.assertEqual(_values(new), [['A', '河岸', False], ['B', '木桥', False]])
        self.assertEqual(old['slots'][1]['lines'], [])
        self.assertEqual(new['slots'][1]['lines'], ['木桥'])
        self.assertEqual(self.api(f"/proofs/{old['proof']}"), old)

    def test_proof_references(self):
        sign = self.sign()
        other = self.sign(sign['template'])
        self.api('/signs/sign-missing/proofs', {'revision': sign['revision']}, status=404)
        path = f"/signs/{sign['sign']}/proofs"
        self.api(path, {'revision': 'sign-rev-missing'}, status=404)
        self.api(path, {'revision': other['revision']}, status=409)
        self.api('/proofs/proof-missing', status=404)
        self.assertEqual(self.count('proofs'), 0)

    def test_edit_rollback(self):
        sign = self.sign()
        old = self.edit(sign, 'A', 'write', text='原稿')
        self.block_commit_after('sign_current', 'UPDATE')
        self.api(f"/signs/{sign['sign']}/edits", {'key': 'A', 'op': 'write', 'text': '改稿'}, status=500)
        self.restart()
        self.assertEqual(self.api(f"/signs/{sign['sign']}"), old)
        self.assertEqual(self.count('sign_revisions'), 2)
        self.assertEqual(self.count('commit_test_child'), 0)
        old_proof = self.proof(old)
        self.assertEqual(old_proof['slots'][0]['lines'], ['原稿'])
        self.issue(old, old_proof)
        self.unblock_commit()
        updated = self.edit(old, 'A', 'write', text='改稿')
        self.assertNotEqual(updated['revision'], old['revision'])
        self.assertEqual(_values(updated), [['A', '改稿', True], ['B', '木桥', False]])
        self.assertEqual(self.count('sign_revisions'), 3)
