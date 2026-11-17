import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('diet',Path(__file__).parents[1]/'skill-diet'/'diet.py')
diet=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(diet)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.base=Path(self.tmp.name); self.root=self.base/'input'; self.root.mkdir()
        (self.root/'SKILL.md').write_text('# Task\nRead all following files.\n[Core](references/core.md)\nIf narration is requested, load `references/voice.md`.\n[Bad](missing.md)\n[External](https://example.com)\n',encoding='utf-8')
        (self.root/'references').mkdir(); (self.root/'references/core.md').write_text('Must validate output.',encoding='utf-8')
        (self.root/'references/voice.md').write_text('Narration instructions',encoding='utf-8')
    def tearDown(self): self.tmp.cleanup()
    def test_references_and_risk(self):
        r=diet.audit(self.root)
        self.assertEqual(len(r['references']),3)
        self.assertEqual([e['status'] for e in r['references']],['exists','exists','unresolved'])
        self.assertTrue(r['references'][1]['conditional_hint'])
        self.assertEqual(r['issues'][0]['type'],'batch_read_candidate')
    def test_copy_is_exact_and_non_destructive(self):
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        out=self.base/'draft'; diet.draft(self.root,out)
        for rel,raw in before.items():
            self.assertEqual((self.root/rel).read_bytes(),raw)
            self.assertEqual((out/'original'/rel).read_bytes(),raw)
        self.assertFalse(json.loads((out/'plan.json').read_text(encoding='utf-8'))['automatic_switching'])
    def test_no_overwrite(self):
        with self.assertRaises(ValueError): diet.draft(self.root,self.root)
        with self.assertRaises(ValueError): diet.draft(self.root,self.root/'child')
        with self.assertRaises(ValueError): diet.draft(self.root,self.base)
        out=self.base/'output'; out.mkdir()
        with self.assertRaises(ValueError): diet.draft(self.root,out)
    def test_symlink_denied(self):
        (self.root/'bad').symlink_to(self.base)
        with self.assertRaises(ValueError): diet.audit(self.root)
    def test_outside_reference(self):
        (self.root/'SKILL.md').write_text('[Outside](../secret.md)')
        self.assertEqual(diet.audit(self.root)['references'][0]['status'],'outside_root')
    def test_size_limit(self):
        (self.root/'huge.bin').write_bytes(b'0'*(diet.MAX_FILE+1))
        with self.assertRaises(ValueError): diet.audit(self.root)
    def test_missing_entry(self):
        (self.root/'SKILL.md').unlink()
        with self.assertRaises(ValueError): diet.audit(self.root)
    def test_identical_files(self):
        (self.root/'copy.md').write_bytes((self.root/'references/core.md').read_bytes())
        self.assertEqual(len(diet.audit(self.root)['identical_files']),1)
    def test_payload_not_read(self):
        self.assertIsNone(diet.BATCH.search("payload installed all"))
    def test_no_script_execution(self):
        (self.root/'evil.py').write_text('raise Exception("must not execute")')
        self.assertEqual(diet.audit(self.root)['summary']['files'],4)

if __name__=='__main__': unittest.main()
