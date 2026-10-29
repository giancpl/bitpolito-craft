import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/bitpolito'))
import brand
import import_figma

class BrandImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.target=self.root/'brand'
        shutil.copytree(brand.BRAND,self.target)
    def tearDown(self): self.tmp.cleanup()
    def test_valid_package_and_deterministic_generation(self):
        brand.generated(self.target)
        before={str(x.relative_to(self.target)):x.read_bytes() for x in self.target.rglob('*') if x.is_file()}
        brand.generated(self.target)
        self.assertEqual(before,{str(x.relative_to(self.target)):x.read_bytes() for x in self.target.rglob('*') if x.is_file()})
    def test_import_is_repeatable(self):
        source=self.root/'exports';shutil.copytree(self.target,source)
        brand.import_manual(source,self.target)
        one=(self.target/'provenance.json').read_bytes()
        brand.import_manual(source,self.target)
        self.assertEqual(one,(self.target/'provenance.json').read_bytes())
    def test_invalid_export_keeps_previous_package(self):
        source=self.root/'exports';shutil.copytree(self.target,source)
        (source/'runtime/bull.png').write_bytes(b'bad')
        before=(self.target/'runtime/bull.png').read_bytes()
        with self.assertRaises(ValueError): brand.import_manual(source,self.target)
        self.assertEqual(before,(self.target/'runtime/bull.png').read_bytes())
    def test_truncated_or_corrupted_png_preserves_entire_package(self):
        original=(self.target/'runtime/bull.png').read_bytes()
        corrupted=bytearray(original);corrupted[29]^=1
        before=brand.hashes(self.target)
        for index,data in enumerate((original[:24],original[:-12],bytes(corrupted))):
            source=self.root/f'broken-{index}';shutil.copytree(self.target,source)
            (source/'runtime/bull.png').write_bytes(data)
            with self.assertRaisesRegex(ValueError,'incomplete or invalid PNG'):
                brand.import_manual(source,self.target)
            self.assertEqual(before,brand.hashes(self.target))
    def test_missing_node_mappings_fail_before_network(self):
        class Never:
            def get(self,*args): self.fail('Unexpected network request')
        before=(self.target/'templates.json').read_bytes()
        with self.assertRaises(ValueError): import_figma.run(brand.read(self.target,'mapping.json'),Never(),self.target)
        self.assertEqual(before,(self.target/'templates.json').read_bytes())
    def test_path_traversal_and_bad_geometry(self):
        for edit in ['path','geometry','font']:
            source=self.root/edit;shutil.copytree(self.target,source)
            if edit=='path':
                data=brand.read(source,'assets.json');data['assets'][0]['file']='../../private.png';brand.dump(source/'assets.json',data)
            elif edit=='geometry':
                data=brand.read(source,'templates.json');data['layouts'][0]['placeholders'][0]['rect'][2]=-1;brand.dump(source/'templates.json',data)
            else:
                data=brand.read(source,'config.json');data['font']='SF Pro';brand.dump(source/'config.json',data)
            with self.assertRaises(ValueError): brand.validate(source)
    def test_failed_api_import_preserves_files(self):
        mappings={'fileKey':'x','layouts':[{'id':x,'nodeId':x} for x in brand.LAYOUTS],'assets':[{'id':'a','nodeId':'asset'}]}
        for reason in ['Figma access denied','Figma rate limit reached','Figma HTTP 500']:
            class Broken:
                def get(self,*args): raise ValueError(reason)
            before=(self.target/'templates.json').read_bytes()
            with self.assertRaisesRegex(ValueError,reason): import_figma.run(mappings,Broken(),self.target)
            self.assertEqual(before,(self.target/'templates.json').read_bytes())

if __name__=='__main__':unittest.main()
