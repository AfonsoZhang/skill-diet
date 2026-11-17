import importlib.util
import tempfile
from pathlib import Path
import unittest
import sqlite3
SPEC=importlib.util.spec_from_file_location('usage',Path(__file__).parents[1]/'skill-diet'/'usage.py')
u=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(u)
END='2026-11-17T00:00:00Z'
class UsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);(self.path/'SKILL.md').write_text('untouched')
        self.db=u.connect(':memory:');u.add(self.db,'demo',self.path)
    def tearDown(self):self.db.close();self.tmp.cleanup()
    def data(self,start='2026-10-01T00:00:00Z',events=None,source='synthetic'):
        return {'source':source,'windows':[{'skill':'demo','start':start,'end':END}],'events':events or []}
    def status(self):return u.inventory(self.db,END,30)[0]
    def test_unknown_not_stale(self):self.assertEqual(self.status()['status'],'unknown')
    def test_full_zero_events_stale_keep(self):
        u.import_usage(self.db,self.data());self.assertTrue(self.status()['actionable_candidate'])
        self.db.execute('UPDATE inventory SET keep=1');self.assertFalse(self.status()['actionable_candidate'])
        self.assertEqual((self.path/'SKILL.md').read_text(),'untouched')
    def test_partial_not_stale(self):
        u.import_usage(self.db,self.data('2026-11-01T00:00:00Z'));self.assertEqual(self.status()['status'],'insufficient_coverage')
    def test_events_count_idempotent(self):
        d=self.data(events=[{'skill':'demo','id':'1','at':'2026-11-16T00:00:00Z'}]);u.import_usage(self.db,d);u.import_usage(self.db,d)
        self.assertEqual(self.status()['count'],1);self.assertEqual(self.status()['status'],'used')
    def test_conflict_rollback(self):
        u.import_usage(self.db,self.data(events=[{'skill':'demo','id':'1','at':END}]))
        d=self.data('2026-09-01T00:00:00Z',events=[{'skill':'demo','id':'1','at':'2026-11-16T00:00:00Z'}])
        with self.assertRaises(ValueError):u.import_usage(self.db,d)
        self.assertEqual(self.db.execute('SELECT count(*) FROM windows').fetchone()[0],1)
    def test_unknown_skill_rejected(self):
        d=self.data();d['windows'][0]['skill']='other'
        with self.assertRaises(sqlite3.IntegrityError):u.import_usage(self.db,d)
    def test_outside_window_rejected(self):
        with self.assertRaises(ValueError):u.import_usage(self.db,self.data(events=[{'skill':'demo','id':'1','at':'2026-09-01T00:00:00Z'}]))
    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):u.timestamp('2026-11-17')
    def test_exact_lookback_coverage(self):
        u.import_usage(self.db,self.data('2026-10-18T00:00:00Z'))
        self.assertEqual(self.status()['status'],'stale_candidate')
    def test_event_at_inclusive_boundary(self):
        u.import_usage(self.db,self.data('2026-10-18T00:00:00Z',events=[{'skill':'demo','id':'boundary','at':'2026-10-18T00:00:00Z'}]))
        self.assertEqual(self.status()['status'],'used')
    def test_nonstring_timestamp_rejected(self):
        with self.assertRaises(ValueError):u.timestamp(None)
    def test_multiple_sources_conservative(self):
        u.import_usage(self.db,self.data());u.import_usage(self.db,self.data('2026-11-01T00:00:00Z',source='second'))
        self.assertFalse(self.status()['stale_candidate'])
    def test_windows_union_and_gap(self):
        self.assertTrue(u.covered([('a','b'),('b','d')],'a','d'))
        self.assertFalse(u.covered([('a','b'),('c','d')],'a','d'))
    def test_timezone_normalization(self):
        self.assertEqual(u.timestamp('2026-11-17T08:00:00+08:00'),u.timestamp(END))
    def test_old_event_count_and_future_asof(self):
        u.import_usage(self.db,self.data(events=[{'skill':'demo','id':'1','at':'2026-10-02T00:00:00Z'}]))
        self.assertEqual(self.status()['count'],1);self.assertTrue(self.status()['stale_candidate'])
        self.assertEqual(u.inventory(self.db,'2026-09-01T00:00:00Z',30)[0]['status'],'unknown')
if __name__=='__main__':unittest.main()
