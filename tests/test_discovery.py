import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'skill-diet' / 'discovery.py'
spec = importlib.util.spec_from_file_location('discovery', MODULE)
discovery = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = discovery
spec.loader.exec_module(discovery)


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def skill(self, relative, content='---\nname: Example\n---\nBody'):
        path = self.root / relative / 'SKILL.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def test_nested_system_plugin_and_cache_labels(self):
        self.skill('.system/tool')
        cached = self.skill('plugins/cache/vendor/version/skills/demo')
        other = self.skill('custom-cache/skill')
        result = discovery.discover([self.root], cache_roots=[other.parent.parent])
        self.assertEqual(len(result['skills']), 3)
        by_path = {s['canonical_path']: s for s in result['skills']}
        for path in (cached, other):
            self.assertEqual(by_path[str(path)]['paths'][0]['source_kind'], 'plugin_cache')
        self.assertTrue(all(s['host_activity']['state'] == 'unknown' for s in result['skills']))
        self.assertEqual(by_path[str(cached)]['name'], 'Example')
        self.assertEqual(by_path[str(cached)]['entry_sha256'], hashlib.sha256(cached.read_bytes()).hexdigest())

    def test_symlink_alias_and_cycle(self):
        path = self.skill('real/skill')
        try:
            (self.root / 'alias').symlink_to(self.root / 'real', target_is_directory=True)
            (self.root / 'real' / 'loop').symlink_to(self.root, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Directory symlinks unavailable')
        result = discovery.discover([self.root])
        self.assertEqual(len(result['skills']), 1)
        self.assertEqual(len(result['skills'][0]['paths']), 2)
        self.assertTrue(any(p['is_alias'] for p in result['skills'][0]['paths']))
        self.assertTrue(any(i['code'] == 'symlink_cycle' for i in result['issues']))

    def test_overlapping_duplicate_roots(self):
        path = self.skill('a/b')
        result = discovery.discover([self.root, path.parent, self.root, path])
        self.assertEqual(len(result['skills']), 1)
        self.assertEqual(len(result['skills'][0]['paths']), 1)
        self.assertEqual(len(result['roots']), 3)

    def test_missing_and_broken_roots(self):
        missing = self.root / 'missing'
        result = discovery.discover([missing])
        self.assertEqual(result['issues'][0]['code'], 'missing_path')
        try:
            broken = self.root / 'broken'
            broken.symlink_to(missing)
        except (OSError, NotImplementedError):
            return
        self.assertEqual(discovery.discover([broken])['issues'][0]['code'], 'broken_link')

    def test_budgets_and_exclusions(self):
        self.skill('a')
        self.skill('b')
        self.skill('.git/hidden')
        result = discovery.discover([self.root], max_skills=1)
        self.assertEqual(len(result['skills']), 1)
        self.assertTrue(result['summary']['truncated'])
        self.assertIn('excluded_directory', {i['code'] for i in result['issues']})
        limited = discovery.discover([self.root], max_directories=1)
        self.assertTrue(limited['summary']['truncated'])
        self.assertFalse(limited['skills'])
        with self.assertRaises(ValueError):
            discovery.discover([self.root], max_skills=0)

    def test_metadata_bounds_invalid_utf8_and_unsupported_yaml(self):
        path = self.skill('large', '---\nname: [unsupported, yaml]\n---\n' + 'x' * 70000)
        result = discovery.discover([self.root])
        self.assertEqual(result['skills'][0]['name'], 'large')
        self.assertIn('metadata_truncated', {i['code'] for i in result['issues']})
        path.write_bytes(b'\xff')
        self.assertEqual(discovery.discover([path])['issues'][0]['code'], 'utf8_decode')

    def test_trusted_adapter_explicit_states_and_absence_unknown(self):
        active = self.skill('a')
        inactive = self.skill('b')
        self.skill('c')
        observation = discovery.HostObservation('host', 'adapter', (str(active),),
                                                (str(inactive.parent),), '2026-11-17')
        result = discovery.discover([self.root], host_observation=observation)
        self.assertEqual([s['host_activity']['state'] for s in result['skills']],
                         ['confirmed_active', 'confirmed_inactive', 'unknown'])
        with self.assertRaises(TypeError):
            discovery.discover([self.root], host_observation={'active_paths': [str(active)]})
        conflict = discovery.HostObservation('host', 'adapter', (str(active),), (str(active),), '2026-11-17')
        result = discovery.discover([self.root], host_observation=conflict)
        self.assertEqual(result['skills'][0]['host_activity']['state'], 'unknown')
        self.assertIn('conflicting_host_observation', {i['code'] for i in result['issues']})

    def test_oversize_sparse_entry_is_skipped_without_read(self):
        from unittest.mock import patch
        path = self.skill('giant')
        with path.open('r+b') as stream:
            stream.truncate(100_000_000)
        with patch('builtins.open', side_effect=AssertionError('Must not open oversize entry')):
            result = discovery.discover([path])
        item = result['skills'][0]
        self.assertEqual(item['entry_bytes'], 100_000_000)
        self.assertIsNone(item['entry_sha256'])
        self.assertEqual(item['entry_read']['state'], 'skipped')
        self.assertTrue(result['summary']['truncated'])
        self.assertEqual(item['host_activity']['state'], 'unknown')

    def test_empty_host_provenance_rejected(self):
        path = self.skill('a')
        for host, source, observed in [('', 'adapter', 'today'), ('host', ' ', 'today'),
                                       ('host', 'adapter', '')]:
            observation = discovery.HostObservation(host, source, (str(path),), (), observed)
            with self.assertRaises(ValueError):
                discovery.discover([self.root], host_observation=observation)

    def test_iterative_deep_walk_and_directory_budget(self):
        current = self.root
        directories = []
        try:
            for _ in range(160):
                current = current / 'd'
                current.mkdir()
                directories.append(current)
            entry = current / 'SKILL.md'
            entry.write_text('Deep', encoding='utf-8')
            # A low recursion limit exposes recursive traversal without creating
            # platform path-length problems or recursive tempfile cleanup.
            original_limit = sys.getrecursionlimit()
            try:
                sys.setrecursionlimit(120)
                result = discovery.discover([self.root])
            finally:
                sys.setrecursionlimit(original_limit)
            self.assertEqual(len(result['skills']), 1)
            limited = discovery.discover([self.root], max_directories=100)
            self.assertTrue(limited['summary']['truncated'])
            self.assertEqual(limited['summary']['directories_visited'], 100)
        finally:
            (current / 'SKILL.md').unlink(missing_ok=True)
            for directory in reversed(directories):
                directory.rmdir()


if __name__ == '__main__':
    unittest.main()
