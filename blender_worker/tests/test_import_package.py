"""Package validation tests; Blender is only needed for the separate smoke test."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('kfs_blender_import_test', ROOT/'import_package.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.package = Path(self.temporary.name)/'package'
        shutil.copytree(ROOT/'tests'/'fixtures'/'nested-mirror', self.package)
        self.manifest = self.package/'manifest.json'
        self.data = json.loads(self.manifest.read_text(encoding='utf-8'))

    def reject(self):
        self.manifest.write_text(json.dumps(self.data),encoding='utf-8')
        with self.assertRaises((ValueError,KeyError)):
            worker.load_package(self.package)

    def test_valid_shared_multibody_nested_mirrored_fixture(self):
        data, meshes = worker.load_package(self.package)
        self.assertEqual(len(data['instances']),4)
        self.assertEqual(len(meshes),3)
        self.assertLess(worker.determinant(data['instances'][-1]['local_to_world_mm']),0)

    def test_duplicate_instances(self):
        self.data['instances'].append(copy.deepcopy(self.data['instances'][0]))
        self.reject()

    def test_duplicate_definitions(self):
        self.data['components'].append(copy.deepcopy(self.data['components'][0]))
        self.reject()

    def test_duplicate_body_identity(self):
        refs = [g for d in self.data['components'] for g in d['geometry_refs']]
        refs[1]['body_id']=refs[0]['body_id']
        self.reject()

    def test_path_escape(self):
        self.data['components'][0]['geometry_refs'][0]['path']='../escape.obj'
        self.reject()

    def test_wrong_units(self):
        self.data['coordinates']['units']='cm'
        self.reject()

    def test_singular_transform(self):
        self.data['instances'][-1]['local_to_world_mm']=[0]*16
        self.reject()

    def test_nonfinite_transform(self):
        self.data['instances'][-1]['local_to_world_mm'][0]=float('nan')
        self.reject()

    def test_wrong_ownership(self):
        self.data['instances'][-1]['geometry_refs']=[]
        self.reject()

    def test_wrong_bounds(self):
        self.data['instances'][-1]['world_bounds_mm']['max'][0]+=10
        self.reject()

    def test_checksum_detects_tampering(self):
        reference=self.data['components'][0]['geometry_refs'][0]['path']
        with (self.package/reference).open('a') as stream:
            stream.write('# changed\n')
        with self.assertRaisesRegex(ValueError,'checksum'):
            worker.load_package(self.package)

    def test_triangle_indices(self):
        path=Path(self.temporary.name)/'bad.obj'
        path.write_text('v 0 0 0\nf 1 1 2\n')
        with self.assertRaises(ValueError): worker.read_obj(path)


if __name__=='__main__':
    unittest.main()
