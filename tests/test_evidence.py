import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('evidence', Path(__file__).resolve().parents[1] / 'skill-diet/evidence.py')
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def report(self, text, extra=None):
        entry = self.root / 'SKILL.md'
        entry.write_text(text)
        skill = dict(id='s', name='s', canonical_path=str(entry), paths=[])
        return evidence.analyze({'skills': [skill] + (extra or [])})

    def test_missing_and_false_positives(self):
        report = self.report('Title\n[read](./references/missing.md)\n[external](https://example.com/missing.md)\n[repo](other-repo/file.md)\n`[code](./references/code.md)`\n```md\n[example](./references/no.md)\n```\nGenerate [output](./references/output.md)\n')
        defects = [f for f in report['findings'] if f['category'] == 'defect']
        self.assertEqual(len(defects), 1)
        self.assertEqual(defects[0]['line'], 2)
        self.assertIn('Title', defects[0]['context'])
        self.assertTrue(Path(defects[0]['path']).is_absolute())
        self.assertTrue(any(f['rule'] == 'dynamic-reference' for f in report['findings']))

    def test_alias_and_binary_do_not_block_entry(self):
        (self.root / 'assets').mkdir()
        (self.root / 'assets/blob.bin').write_bytes(b'\x00' * (evidence.MAX_TEXT_BYTES + 1))
        alias = self.root / 'alias.md'
        alias.symlink_to(self.root / 'SKILL.md')
        report = self.report('[asset](./assets/blob.bin)\n[missing](./references/no.md)',
                             [dict(id='alias', name='s', canonical_path=str(alias))])
        self.assertEqual(len(report['coverage']), 1)
        self.assertEqual(sum(f['category'] == 'defect' for f in report['findings']), 1)
        self.assertTrue(report['coverage'][0]['skipped'])

    def test_symlink_escape(self):
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'private.md').write_text('[missing](./references/secret.md)')
        skill = self.root / 'skill'
        skill.mkdir()
        (skill / 'references').symlink_to(outside, target_is_directory=True)
        (skill / 'SKILL.md').write_text('[private](./references/private.md)')
        report = evidence.analyze({'skills': [dict(id='s', name='s', canonical_path=str(skill / 'SKILL.md'))]})
        self.assertEqual(report['coverage'][0]['files_read'], 1)
        self.assertFalse(any(f['category'] == 'defect' for f in report['findings']))

    def test_optional_read_and_credentials(self):
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/a.py').write_text('password = "never quote me"\nprint(password)\n')
        report = self.report('If needed read all references files.\nAlways read all references files.\n[script](./scripts/a.py)')
        self.assertEqual(sum(f['rule'] == 'read-all' for f in report['findings']), 1)
        credential = next(f for f in report['findings'] if f['rule'] == 'credential-print')
        self.assertEqual(credential['line'], 2)
        self.assertNotIn('never quote me', str(report))
        self.assertIn('unknown', evidence.render_markdown(report))

    def test_oversized_support_and_duplicate_roots(self):
        (self.root / 'references').mkdir()
        (self.root / 'references/big.md').write_text('x' * (evidence.MAX_TEXT_BYTES + 1))
        text = '[big](./references/big.md)\n[missing](./references/no.md)'
        second = self.root / 'second'
        second.mkdir()
        (second / 'SKILL.md').write_text(text)
        report = self.report(text, [dict(id='second', name='s', canonical_path=str(second / 'SKILL.md'))])
        self.assertTrue(any(f['rule'] == 'identical-entry' for f in report['findings']))
        self.assertTrue(any(f['rule'] == 'duplicate-name' for f in report['findings']))
        self.assertTrue(any(f['rule'] == 'missing-local-resource' for f in report['findings']))
        self.assertTrue(any(s['reason'] == 'text size limit' for s in report['coverage'][0]['skipped']))

    def test_incomplete_discovery_and_skipped_entry(self):
        entry = self.root / 'SKILL.md'
        entry.write_text('x' * (evidence.MAX_TEXT_BYTES + 1))
        issue = {'kind': 'missing_root', 'path': '/missing'}
        report = evidence.analyze({'skills': [dict(id='s', name='s', canonical_path=str(entry),
            entry_sha256=None, entry_read={'state': 'skipped', 'reason': 'entry_byte_budget'})],
            'summary': {'truncated': True}, 'issues': [issue]},
            host_context={'commands': {}, 'tool_names': ['a'], 'model_names': [], 'source': 'operator_reported_file'})
        self.assertEqual(report['summary']['skills_audited'], 0)
        self.assertEqual(report['summary']['skills_skipped'], 1)
        self.assertEqual(report['discovery_issues'], [issue])
        self.assertEqual(report['host_context_coverage']['supplied_unchecked_fields'], ['tool_names', 'model_names'])
        rendered = evidence.render_markdown(report)
        for expected in ('missing_root', 'truncated', 'entry_byte_budget', 'operator_reported_file'):
            self.assertIn(expected, rendered)

    def test_host_context_is_explicit(self):
        report = self.report('Requires frobnicate command.')
        self.assertFalse(report['findings'])
        entry = self.root / 'SKILL.md'
        report = evidence.analyze({'skills': [dict(id='s', name='s', canonical_path=str(entry))]},
                                  host_context={'commands': {'frobnicate': False}})
        self.assertEqual(report['findings'][0]['category'], 'host_prerequisite')


if __name__ == '__main__':
    unittest.main()
