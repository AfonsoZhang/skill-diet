"""Meaningful checks of synthetic inputs, isolation, budgets and scoring."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('synthetic_review', Path(__file__).parents[1] / 'benchmarks/review.py')
b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(b)


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'run'
        b.prepare(self.root)

    def test_reproducible_seed_and_separate_truth(self):
        other = Path(self.temp.name) / 'other'
        b.prepare(other)
        self.assertEqual(b.digest(self.root/'library'), b.digest(other/'library'))
        self.assertEqual(8, len(list((self.root/'library').rglob('SKILL.md'))))
        self.assertNotIn('truth', b.action(self.root, 'plain', 'list'))
        with self.assertRaises(ValueError):
            b.action(self.root, 'plain', 'read', '../private/truth.json')
        with self.assertRaises(ValueError):
            b.action(self.root, 'plain', 'inspect')

    def test_recorded_fixture_hash_is_portable(self):
        if not (self.root/'library/user/alias').is_symlink() or not (self.root/'library/project/team/cycle').is_symlink():
            self.skipTest('Recorded fixture includes symlinks unavailable on this host')
        recorded = Path(__file__).parents[1]/'benchmarks/results/seed-17/manifest.json'
        self.assertEqual(json.loads(recorded.read_text())['input_hash'], b.digest(self.root/'library'))

    def test_tamper_and_budget_rejected(self):
        p = next((self.root/'library').rglob('SKILL.md'))
        p.write_text('changed')
        with self.assertRaises(ValueError):
            b.load(self.root)

    def test_manifest_tamper_rejected(self):
        p = self.root/'manifest.json'
        value = json.loads(p.read_text())
        value['seed'] += 1
        b.write(p, value)
        with self.assertRaises(ValueError):
            b.load(self.root)

    def test_operations_and_timeout(self):
        for _ in range(12):
            b.action(self.root, 'plain', 'list')
        with self.assertRaises(ValueError):
            b.action(self.root, 'plain', 'list')
        b.action(self.root, 'aided', 'list')
        p = self.root/'aided.json'
        state = json.loads(p.read_text())
        state['start'] -= 241
        b.write(p, state)
        with self.assertRaises(ValueError):
            b.action(self.root, 'aided', 'list')

    def test_inspect_charges_same_budget_and_keeps_report(self):
        report = {'findings': [], 'coverage': {'status': 'bounded'}, 'limitations': ['synthetic']}
        with patch.object(b, 'inspect', return_value=report):
            result = b.action(self.root, 'aided', 'inspect')
        self.assertEqual(report, json.loads(result))
        state = json.loads((self.root/'aided.json').read_text())
        self.assertEqual(1, state['operations'])
        self.assertEqual(1, state['tool_calls'])
        self.assertEqual(len(result), state['returned_characters'])
        state['returned_characters'] = b.BUDGET['characters']
        b.write(self.root/'aided.json', state)
        with self.assertRaises(ValueError):
            b.action(self.root, 'aided', 'list')

    def test_score_duplicates_false_positives_and_misses(self):
        truth = json.loads((self.root/'private/truth.json').read_text())
        f = {'rule': truth[0]['rule'], 'path': truth[0]['path'], 'line': 7,
             'category': 'defect', 'explanation': 'Required file absent.'}
        false = dict(f, rule='backend-mismatch')
        submission = Path(self.temp.name)/'findings.json'
        b.write(submission, [f, f, false])
        for condition in ('plain', 'aided'):
            b.action(self.root, condition, 'submit', submission=submission)
        s = b.score(self.root)['scores']['plain']
        self.assertEqual((1, 1, 6), (s['true_positives'], s['false_positives'], s['misses']))
        self.assertIsNone(s['tokens'])
        self.assertIsNone(s['false_positive_rate'])

    def test_helper_truth_and_markdown_reference(self):
        truth = json.loads((self.root/'private/truth.json').read_text())
        missing = next(t for t in truth if t['rule'] == 'missing-resource')
        self.assertIn('[format guide](references/format.md)', (self.root/'library'/missing['path']).read_text())
        helper = next(t for t in truth if t['rule'] == 'credential-output')
        self.assertTrue(helper['path'].endswith('scripts/diagnose.py'))
        lines = (self.root/'library'/helper['path']).read_text().splitlines()
        self.assertEqual('print(session_cookie)', lines[helper['lines'][0]-1])
        self.assertIn('synthetic-session', lines[1])

    def test_unknown_condition_and_edited_effort_rejected(self):
        with self.assertRaises(ValueError):
            b.action(self.root, '../../outside', 'list')
        self.assertFalse((Path(self.temp.name)/'outside.json').exists())
        submission = Path(self.temp.name)/'empty.json'
        b.write(submission, [])
        for condition in ('plain', 'aided'):
            b.action(self.root, condition, 'submit', submission=submission)
        statepath = self.root/'plain.json'
        state = json.loads(statepath.read_text())
        state['read_calls'] += 1
        b.write(statepath, state)
        with self.assertRaisesRegex(ValueError, 'aggregate effort'):
            b.score(self.root)

    def test_strict_submission(self):
        with self.assertRaises(ValueError):
            b.findings([{'rule': 'missing-resource'}], self.root/'library')
        f = {'rule': 'missing-resource', 'path': '../manifest.json', 'line': 1,
             'category': 'defect', 'explanation': 'bad'}
        with self.assertRaises(ValueError):
            b.findings([f], self.root/'library')

if __name__ == '__main__':
    unittest.main()
