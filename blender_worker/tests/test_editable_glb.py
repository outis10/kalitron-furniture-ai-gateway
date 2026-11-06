"""Editor metadata must be snapshot-safe and leave geometry bytes untouched."""
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('editable_glb_test', ROOT/'editable_glb.py')
glb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(glb)


class EditableGlbTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'presets/white-matte-preview.json').read_text())
        self.config['module_finishes']={'source_export_id':'export-A','groups':{'LOWER':['module']},'instances':{'module':{'FRONT':'WHITE_MATTE'}},'role_families':{'DOOR':'FRONT'}}
        self.package={'export_id':'export-A','instances':[
            dict(instance_id='module',definition_id='mod-def',parent_instance_id=None),
            dict(instance_id='door',definition_id='door-def',parent_instance_id='module',role='DOOR')]}
        self.doc={'asset':{'version':'2.0'},'nodes':[{'mesh':0,'extras':{'kfs_instance_id':'door'}}], 'buffers':[{'byteLength':4}]}
        encoded=json.dumps(self.doc).encode();encoded+=b' '*(-len(encoded)%4)
        body=struct.pack('<II',len(encoded),0x4E4F534A)+encoded+struct.pack('<II',4,0x004E4942)+b'\x01\x02\x03\x04'
        self.original=struct.pack('<III',0x46546C67,2,len(body)+12)+body

    def test_metadata_is_self_contained_and_geometry_is_identical(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(sys,'path',[str(ROOT),*sys.path]):
            path=Path(directory)/'kitchen.glb';path.write_bytes(self.original)
            glb.attach_editor(path,self.package,self.config)
            doc,chunks=glb.read_glb(path.read_bytes())
            self.assertEqual(chunks,glb.read_glb(self.original)[1])
            self.assertEqual(doc['nodes'],self.doc['nodes'])
            self.assertEqual(doc['buffers'],self.doc['buffers'])
            editor=doc['asset']['extras']['kfs_finish_editor']
            self.assertEqual(editor['config'],self.config)
            self.assertEqual(editor['source_export_id'],'export-A')
            self.assertNotIn('entityToken',json.dumps(editor))

    def test_stale_or_duplicate_groups_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(sys,'path',[str(ROOT),*sys.path]):
            path=Path(directory)/'kitchen.glb';path.write_bytes(self.original)
            self.config['module_finishes']['groups']['UPPER']=['module']
            with self.assertRaises(ValueError):glb.attach_editor(path,self.package,self.config)
            self.config['module_finishes']['groups']={'LOWER':['unknown']}
            with self.assertRaises(ValueError):glb.attach_editor(path,self.package,self.config)
            self.config['module_finishes']['groups']={'LOWER':['module']}
            self.config['module_finishes']['source_export_id']='export-B'
            with self.assertRaises(ValueError):glb.attach_editor(path,self.package,self.config)

    def test_truncated_and_foreign_glbs_are_rejected(self):
        with self.assertRaises(ValueError):glb.read_glb(self.original[:-1])
        with tempfile.TemporaryDirectory() as directory, patch.object(sys,'path',[str(ROOT),*sys.path]):
            path=Path(directory)/'kitchen.glb';path.write_bytes(self.original)
            self.package['instances'][1]['instance_id']='another-door'
            with self.assertRaises(ValueError):glb.attach_editor(path,self.package,self.config)


if __name__=='__main__':unittest.main()
