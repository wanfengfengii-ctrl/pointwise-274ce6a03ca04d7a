from tests.support import HTTPCase, scenario


class PersistenceTests(HTTPCase):
    def test_release_write_failure(self):
        sign = self.sign()
        old_proof = self.proof(sign)
        old = self.issue(sign, old_proof)
        old_path = f"/releases/{old['release']}"
        before = self.client.request(old_path)
        self.assertEqual(before.status, 200, before.body)

        edited = self.edit(sign, 'A', 'write', text='新稿')
        proof = self.proof(edited)
        self.assertEqual(proof['overflow'], [])
        self.block_commit_after('releases', 'INSERT')
        issue_path = f"/signs/{sign['sign']}/releases"
        failed = self.client.request(issue_path, {'proof': proof['proof']})
        self.assertEqual(failed.status, 500, failed.body)
        self.assertNotIn('release', failed.body)
        self.restart()
        count = self.count('releases')
        child_count = self.count('commit_test_child')
        self.assertEqual(count, 1)
        self.assertEqual(child_count, 0)
        repeat = self.client.request(old_path)
        self.assertEqual(repeat.raw, before.raw)
        self.api(f"/proofs/{proof['proof']}")
        self.api('/releases/release-2', status=404)

        self.unblock_commit()
        retry = self.client.request(issue_path, {'proof': proof['proof']})
        self.assertEqual(retry.status, 201, retry.body)
        path = f"/releases/{retry.body['release']}"
        receipt = self.api(path)
        self.assertEqual(receipt['source'], retry.body['source'])
        self.assertEqual(receipt['source']['proof'], proof['proof'])
        self.assertEqual(receipt['source']['revision'], edited['revision'])
        self.assertEqual(receipt['source']['template'], sign['template'])
        self.assertIn('<div class="line">新稿</div>', receipt['html'])
        self.assertEqual(self.count('releases'), 2)
        self.restart()
        self.assertEqual(self.api(path), receipt)
        scenario(
            'v8', {'existing_receipts': 1, 'text': '新稿', 'commit_failure': 'deferred foreign key'},
            {'status': 500, 'receipts_after_reopen': 1, 'deferred_rows_after_reopen': 0},
            {'status': failed.status, 'receipts_after_reopen': count, 'deferred_rows_after_reopen': child_count},
            {'old_receipt_unchanged': True, 'retry_status': 201, 'receipt_count': 2},
            {'old_receipt_unchanged': repeat.raw == before.raw, 'retry_status': retry.status,
             'receipt_count': self.count('releases')},
            ['release/database.py', 'release/http.py', 'release/issue.py', 'release/retrieval.py'],
            '延迟外键在发阅行写入后阻止提交。重开只能领回已有的一件，移除触发器后原校样可再办。',
        )
