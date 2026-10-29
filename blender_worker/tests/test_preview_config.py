"""Meaningful configuration and finish-resolution checks without Blender."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('kfs_preview_config_test',ROOT/'preview_config.py')
config_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(config_module)


class PreviewConfigTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'presets'/'white-matte-preview.json').read_text())

    def test_preset_validates(self):
        config_module.validate_config(self.config)

    def test_explicit_override_precedence(self):
        self.config['definition_assignments']['d']='LIGHT_COUNTERTOP'
        self.config['instance_assignments']['i']='BLACK_PROFILE'
        instance={'instance_id':'i','definition_id':'d','role':'DOOR'}
        self.assertEqual(config_module.resolve_material(self.config,instance),('BLACK_PROFILE','instance'))
        self.config['instance_assignments'].clear()
        self.assertEqual(config_module.resolve_material(self.config,instance),('LIGHT_COUNTERTOP','definition'))
        self.config['definition_assignments'].clear()
        self.assertEqual(config_module.resolve_material(self.config,instance),('WHITE_MATTE','role'))

    def test_unknown_role_is_reportable_fallback(self):
        self.assertEqual(config_module.resolve_material(self.config,{'role':'CUSTOM'}),
                         ('UNRESOLVED_NEUTRAL','diagnostic_fallback'))

    def test_unknown_material_rejected(self):
        self.config['role_assignments']['DOOR']='MISSING'
        with self.assertRaises(ValueError): config_module.validate_config(self.config)

    def test_nonfinite_color_rejected(self):
        self.config['materials']['WHITE_MATTE']['color'][0]=float('nan')
        with self.assertRaises(ValueError): config_module.validate_config(self.config)

    def test_invalid_render_settings_rejected(self):
        self.config['render']['samples']=100000
        with self.assertRaises(ValueError): config_module.validate_config(self.config)

    def test_unconfirmed_cannot_be_mislabeled_final(self):
        self.config['illustrative']=False
        with self.assertRaises(ValueError): config_module.validate_config(self.config)

    def test_unknown_option_rejected(self):
        self.config['run_python']='unreviewed-code'
        with self.assertRaises(ValueError): config_module.validate_config(self.config)


if __name__=='__main__':
    unittest.main()
