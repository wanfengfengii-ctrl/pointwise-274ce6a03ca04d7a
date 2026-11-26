from tests.support import HTTPCase, scenario


class ProofTests(HTTPCase):
    def test_wrapping_and_overflow(self):
        sign = self.sign()
        fit = self.edit(sign, 'A', 'write', text='甲乙丙丁')
        accepted = self.proof(fit)
        self.assertEqual(accepted['slots'][0]['lines'], ['甲乙', '丙丁'])
        self.assertEqual(accepted['overflow'], [])
        accepted_reply = self.client.request(f"/signs/{sign['sign']}/releases", {'proof': accepted['proof']})
        self.assertEqual(accepted_reply.status, 201, accepted_reply.body)
        release_id = accepted_reply.body['release']
        fixed = self.api(f'/releases/{release_id}')
        self.assertIn('<div class="line">丙丁</div>', fixed['html'])
        self.assertEqual(fixed['source']['proof'], accepted['proof'])

        long = self.edit(fit, 'A', 'write', text='甲乙丙丁戊')
        rejected = self.proof(long)
        self.assertEqual(rejected['revision'], long['revision'])
        self.assertEqual([item['key'] for item in rejected['slots']], ['A', 'B'])
        self.assertEqual(rejected['slots'][0]['lines'], ['甲乙', '丙丁', '戊'])
        self.assertTrue(rejected['slots'][0]['overflow'])
        self.assertFalse(rejected['slots'][1]['overflow'])
        self.assertEqual(rejected['overflow'], ['A'])
        rejected_reply = self.client.request(f"/signs/{sign['sign']}/releases", {'proof': rejected['proof']})
        self.assertEqual(rejected_reply.status, 409, rejected_reply.body)
        self.assertEqual(self.count('releases'), 1)
        scenario(
            'v7', {'width': 2, 'max_lines': 2, 'texts': ['甲乙丙丁', '甲乙丙丁戊']},
            {'lines': [['甲乙', '丙丁'], ['甲乙', '丙丁', '戊']], 'overflow': [[], ['A']]},
            {'lines': [accepted['slots'][0]['lines'], rejected['slots'][0]['lines']],
             'overflow': [accepted['overflow'], rejected['overflow']]},
            [201, 409], [accepted_reply.status, rejected_reply.status],
            ['proofs/resolve.py', 'proofs/wrap.py', 'proofs/render.py', 'release/eligibility.py'],
            '依次每两个码点一组。四字得两行，五字得三行，第三行戊使 A 超过两行上限。',
        )

    def test_line_boundaries(self):
        sign = self.sign()
        edited = self.edit(sign, 'A', 'write', text='甲😀\n\n乙\n')
        edited = self.edit(edited, 'B', 'write', text='')
        proof = self.proof(edited)
        self.assertEqual(proof['slots'][0]['lines'], ['甲😀', '', '乙', ''])
        self.assertEqual(proof['slots'][1]['lines'], [])
        self.assertTrue(proof['slots'][0]['overridden'])
        self.assertTrue(proof['slots'][1]['overridden'])
        self.assertEqual([slot['overflow'] for slot in proof['slots']], [True, False])
        self.assertEqual(proof['overflow'], ['A'])
        self.issue(edited, proof, status=409)
        self.assertEqual(self.count('releases'), 0)
