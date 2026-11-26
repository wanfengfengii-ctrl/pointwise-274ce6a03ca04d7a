from tests.support import HTTPCase, two_slots


class ReleaseTests(HTTPCase):
    def test_fixed_receipt(self):
        asset = self.api('/assets', {'name': '渡口', 'kind': 'text', 'body': '渡口说明'}, status=201)
        sign = self.sign(assets=[asset['revision']])
        proof = self.proof(sign)
        issued = self.issue(sign, proof)
        path = f"/releases/{issued['release']}"
        first = self.client.request(path)
        self.assertEqual(first.status, 200, first.body)
        self.assertEqual(first.body['source'], {
            'proof': proof['proof'], 'sign': sign['sign'], 'revision': sign['revision'],
            'template': sign['template'], 'assets': [asset['revision']],
        })
        self.assertEqual(first.body['source'], issued['source'])
        self.assertIn('<div class="line">河岸</div>', first.body['html'])
        edited = self.edit(sign, 'A', 'write', text='改稿')
        self.restart()
        second = self.client.request(path)
        self.assertEqual(second.status, 200, second.body)
        self.assertEqual(first.raw, second.raw)
        self.assertEqual(first.body['html'].encode('utf-8'), second.body['html'].encode('utf-8'))
        self.assertEqual(self.proof(edited)['slots'][0]['lines'], ['改稿'])

    def test_stale_proof(self):
        sign = self.sign()
        old_proof = self.proof(sign)
        edited = self.edit(sign, 'A', 'write', text='现场')
        self.issue(sign, old_proof, status=409)
        self.assertEqual(self.count('releases'), 0)
        self.assertEqual(self.api(f"/proofs/{old_proof['proof']}"), old_proof)
        self.assertEqual(old_proof['slots'][0]['lines'], ['河岸'])
        fresh = self.proof(edited)
        self.assertEqual(fresh['slots'][0]['lines'], ['现场'])
        receipt = self.issue(edited, fresh)
        self.assertEqual(receipt['source']['revision'], edited['revision'])
        self.assertEqual(self.count('releases'), 1)

    def test_wrong_sign(self):
        sign = self.sign()
        other = self.sign(sign['template'])
        self.assertEqual(sign['slots'], other['slots'])
        foreign = self.proof(other)
        self.issue(sign, foreign, status=409)
        self.assertEqual(self.count('releases'), 0)
        self.issue(other, foreign)
        self.assertEqual(self.count('releases'), 1)

    def test_unknown_proof(self):
        sign = self.sign()
        self.issue(sign, {'proof': 'proof-missing'}, status=404)
        self.issue({'sign': 'sign-missing'}, self.proof(sign), status=404)
        self.assertEqual(self.count('releases'), 0)

    def test_exact_sources(self):
        text = self.api('/assets', {'name': '渡口', 'kind': 'text', 'body': '说明'}, status=201)
        image = self.api('/assets', {'name': '桥照', 'kind': 'image', 'alt': '河上木桥'}, status=201)
        template = self.publish()['template']
        for order in ((image, text), (text, image)):
            with self.subTest(order=order):
                revisions = [record['revision'] for record in order]
                sign = self.sign(template, revisions)
                proof = self.proof(sign)
                issued = self.issue(sign, proof)
                self.assertEqual(proof['assets'], revisions)
                self.assertEqual(issued['source'], {
                    'proof': proof['proof'], 'sign': sign['sign'], 'revision': sign['revision'],
                    'template': template, 'assets': revisions,
                })
                self.assertNotEqual(issued['source']['assets'], [record['asset'] for record in order])
                self.assertEqual(self.api(f"/releases/{issued['release']}")['source'], issued['source'])

    def test_literal_text(self):
        layout = two_slots()
        for slot in layout:
            slot['width'] = 16
        layout[0]['label'] = '<右&栏>'
        template = self.publish(layout, title='<河岸&记忆>')
        sign = self.sign(template['template'])
        edited = self.edit(sign, 'A', 'write', text=' 甲&乙 ')
        edited = self.edit(edited, 'B', 'write', text='<渡口>\n')
        proof = self.proof(edited)
        self.assertEqual([slot['lines'] for slot in proof['slots']], [[' 甲&乙 '], ['<渡口>', '']])
        issued = self.issue(edited, proof)
        path = f"/releases/{issued['release']}"
        first = self.client.request(path)
        self.assertEqual(first.status, 200, first.body)
        html = first.body['html']
        self.assertIn('<title>&lt;河岸&amp;记忆&gt;</title>', html)
        self.assertIn('<h2>&lt;右&amp;栏&gt;</h2>', html)
        self.assertIn('<div class="line"> 甲&amp;乙 </div>', html)
        self.assertIn('<div class="line">&lt;渡口&gt;</div>\n<div class="line"></div>', html)
        self.assertIn('white-space:pre', html)
        self.assertLess(html.index('data-slot="A"'), html.index('data-slot="B"'))
        self.restart()
        self.assertEqual(self.client.request(path).raw, first.raw)

    def test_unknown_receipt(self):
        self.api('/releases/release-missing', status=404)
        self.assertEqual(self.count('releases'), 0)

    def test_reinitialize(self):
        sign = self.sign()
        issued = self.issue(sign, self.proof(sign))
        path = f"/releases/{issued['release']}"
        first = self.client.request(path)
        self.assertEqual(first.status, 200, first.body)
        edited = self.edit(sign, 'B', 'write', text='旧渡')
        for reopening in range(2):
            with self.subTest(reopening=reopening):
                self.restart()
                self.assertEqual(self.api(f"/signs/{sign['sign']}"), edited)
                self.assertEqual(self.client.request(path).raw, first.raw)
                proof = self.proof(edited)
                self.assertEqual(proof['revision'], edited['revision'])
                self.assertEqual(proof['slots'][1]['lines'], ['旧渡'])
                self.assertTrue(proof['slots'][1]['overridden'])
        self.assertEqual(self.count('releases'), 1)
        self.assertEqual(self.count('sign_revisions'), 2)
