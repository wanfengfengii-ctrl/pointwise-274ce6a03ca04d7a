from contextlib import closing

from release.database import open_database
from tests.support import HTTPCase, two_slots


class PreparationTests(HTTPCase):
    def test_approved_inputs(self):
        text = self.api('/assets', {
            'name': '渡口说明', 'kind': 'text', 'body': ' 渡口原文\n', 'source': '馆档-017',
        }, status=201)
        image = self.api('/assets', {
            'name': '桥景照片', 'kind': 'image', 'alt': ' 桥下的船 ',
        }, status=201)
        self.assertEqual(len({text['asset'], text['revision'], image['asset'], image['revision']}), 4)
        with closing(open_database(self.path)) as db:
            stored = db.execute('''
                SELECT asset, body, alt, source FROM asset_revisions ORDER BY number
            ''').fetchall()
        self.assertEqual([tuple(row) for row in stored], [
            (text['asset'], ' 渡口原文\n', None, '馆档-017'),
            (image['asset'], None, ' 桥下的船 ', image['asset']),
        ])
        layout = two_slots()
        template = self.publish(layout)
        self.assertNotEqual(template['template'], template['draft'])
        self.assertEqual(template['title'], '河岸记忆')
        self.assertEqual(template['slots'], layout)
        self.assertEqual([slot['key'] for slot in template['slots']], ['A', 'B'])

    def test_publish_once(self):
        template = self.publish()
        self.api(f"/templates/drafts/{template['draft']}/publish", {}, status=409)
        self.api('/templates/drafts/draft-missing/publish', {}, status=404)
        self.assertEqual(self.count('published_templates'), 1)
        sign = self.sign(template['template'])
        self.assertEqual(sign['template'], template['template'])

    def test_missing_alt(self):
        self.api('/assets', {'name': '桥景照片', 'kind': 'image'}, status=400)
        self.assertEqual(self.count('asset_catalog'), 0)
        self.assertEqual(self.count('asset_revisions'), 0)
        image = self.api('/assets', {'name': '桥景照片', 'kind': 'image', 'alt': '河上木桥'}, status=201)
        self.assertTrue(image['revision'])
        self.assertEqual(self.count('asset_revisions'), 1)

    def test_media_payload(self):
        for payload in (
            {'kind': 'video', 'body': '片段'},
            {'kind': 'text', 'alt': '用途不符'},
            {'kind': 'text', 'body': '  '},
            {'kind': 'image', 'alt': 14},
        ):
            with self.subTest(payload=payload):
                self.api('/assets', {'name': '渡口档案', **payload}, status=400)
        self.assertEqual(self.count('asset_catalog'), 0)
        self.assertEqual(self.count('asset_revisions'), 0)

    def test_duplicate_slot(self):
        slots = two_slots()
        slots[1]['key'] = 'A'
        self.api('/templates/drafts', {'title': '双栏', 'slots': slots}, status=400)
        self.assertEqual(self.count('template_drafts'), 0)
        self.assertEqual(self.count('published_templates'), 0)
        slots[1]['key'] = 'B'
        slots[1]['label'] = slots[0]['label']
        valid = self.publish(slots)
        self.assertEqual([slot['key'] for slot in valid['slots']], ['A', 'B'])
        self.assertEqual([slot['label'] for slot in valid['slots']], ['右栏', '右栏'])

    def test_positive_limits(self):
        for field in ('width', 'max_lines'):
            for value in (0, -2, 1.5, 2.0, True, '2'):
                with self.subTest(field=field, value=value):
                    slots = two_slots()
                    slots[0][field] = value
                    self.api('/templates/drafts', {'title': '双栏', 'slots': slots}, status=400)
        self.assertEqual(self.count('template_drafts'), 0)
        self.assertEqual(self.count('published_templates'), 0)
