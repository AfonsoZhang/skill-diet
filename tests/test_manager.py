import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / 'skill-diet' / 'manager.py'


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.skills = self.base / 'skills'
        self.skill = self.skills / 'demo'
        self.skill.mkdir(parents=True)
        (self.skill / 'SKILL.md').write_text('# Example\n', encoding='utf-8')
        self.db = self.base / 'state' / 'inventory.sqlite'

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, code=0):
        proc = subprocess.run([sys.executable, str(CLI), '--db', str(self.db), *map(str, args)],
                              capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(proc.returncode, code, proc.stderr)
        if code:
            self.assertNotIn('Traceback', proc.stderr)
            return proc
        return json.loads(proc.stdout)

    def test_scan_is_explicit_and_does_not_register(self):
        (self.skills / 'not-a-skill').mkdir()
        self.assertEqual([r['suggested_id'] for r in self.run_cli('scan', self.skills)], ['demo'])
        self.assertEqual(len(self.run_cli('scan', self.skill)), 1)
        self.assertFalse(self.db.parent.exists())

    def test_fresh_list_and_invalid_arguments_do_not_create_database(self):
        self.assertEqual(self.run_cli('list'), [])
        self.run_cli('list', '--days', 0, code=2)
        self.run_cli('list', '--as-of', 'invalid', code=2)
        self.run_cli('add', 'demo', self.base, code=2)
        self.assertFalse(self.db.parent.exists())

    def test_persistent_usage_lifecycle(self):
        self.run_cli('add', 'demo', self.skill)
        self.assertEqual(self.run_cli('list')[0]['status'], 'unknown')
        payload = self.base / 'events.json'
        payload.write_text(json.dumps({'source': 'test', 'windows': [
            {'skill': 'demo', 'start': '2026-10-18T00:00:00Z', 'end': '2026-11-17T00:00:00Z'}
        ], 'events': []}), encoding='utf-8')
        self.run_cli('import', payload)
        args = ('--as-of', '2026-11-17T00:00:00Z')
        self.assertEqual(len(self.run_cli('stale', *args)), 1)
        self.run_cli('keep', 'demo', 'on')
        self.assertEqual(self.run_cli('stale', *args), [])
        self.assertEqual(self.run_cli('list', *args)[0]['status'], 'stale_candidate')
        self.assertEqual((self.skill / 'SKILL.md').read_text(), '# Example\n')

    def test_registration_updates_location_and_preserves_keep(self):
        self.run_cli('add', 'demo', self.skill)
        self.run_cli('keep', 'demo', 'on')
        moved = self.skills / 'moved'
        self.skill.rename(moved)
        self.assertFalse(self.run_cli('list')[0]['entry_exists'])
        self.run_cli('add', 'demo', moved)
        item = self.run_cli('list')[0]
        self.assertTrue(item['entry_exists'])
        self.assertTrue(item['keep'])
        self.assertEqual(Path(item['path']), moved.resolve())

    def test_audit_and_draft_do_not_create_database(self):
        self.assertEqual(self.run_cli('audit', self.skill, '--format', 'json')['summary']['files'], 1)
        out = self.base / 'review'
        self.run_cli('draft', self.skill, '--out', out)
        self.assertEqual((out / 'original' / 'SKILL.md').read_bytes(), (self.skill / 'SKILL.md').read_bytes())
        self.run_cli('draft', self.skill, '--out', out, code=2)
        self.assertFalse(self.db.exists())

    def test_malformed_import_is_a_cli_error(self):
        self.run_cli('add', 'demo', self.skill)
        payload = self.base / 'bad.json'
        payload.write_text('{"source":"test","windows":[{"start":null}],"events":[]}', encoding='utf-8')
        self.run_cli('import', payload, code=2)
        self.assertEqual(self.run_cli('list')[0]['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
