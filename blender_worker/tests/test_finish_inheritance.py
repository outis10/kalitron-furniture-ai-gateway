"""Behavioral tests for two-tone modules, shared instances and revision safety."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('module_finish_config_test', ROOT / 'preview_config.py')
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)


def node(key, parent=None, role=None, definition=None, **extra):
    return dict(instance_id=key, definition_id=definition or 'd_' + key,
                parent_instance_id=parent, role=role, **extra)


class ModuleFinishTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'presets/white-matte-preview.json').read_text())
        self.config['definition_assignments'] = {}
        self.config['instance_assignments'] = {}
        self.config['module_finishes'] = {
            'source_export_id': 'snapshot-A',
            'role_families': {'DOOR': 'FRONT', 'COVER_PANEL': 'FRONT',
                              'CARCASS_SIDE': 'CARCASS', 'GOLA_PROFILE': 'GOLA'},
            'project': {'CARCASS': 'WHITE_MATTE', 'GOLA': 'BLACK_PROFILE'},
            'instances': {'lower': {'FRONT': 'BLACK_PROFILE', 'CARCASS': 'WHITE_MATTE'},
                          'upper': {'FRONT': 'WHITE_MATTE', 'CARCASS': 'WHITE_MATTE'}},
            'definitions': {},
        }
        self.nodes = [node('root'), node('lower', 'root', definition='shared-module'),
                      node('upper', 'root', definition='shared-module'),
                      node('lower-door', 'lower', 'DOOR', 'shared-door'),
                      node('upper-door', 'upper', 'DOOR', 'shared-door'),
                      node('filler', 'lower', 'FILLER', finish_target='DOOR'),
                      node('cover', 'upper', 'COVER_PANEL'),
                      node('inside', 'lower', 'CARCASS_SIDE'),
                      node('gola', 'lower', 'GOLA_PROFILE')]
        self.package = {'export_id': 'snapshot-A', 'instances': self.nodes}

    def resolver(self):
        preview.validate_config(self.config)
        return preview.build_module_resolver(self.config, self.package)

    def resolve(self, key):
        return self.resolver().resolve(next(n for n in self.nodes if n['instance_id'] == key))

    def test_shared_definitions_have_independent_placed_finishes(self):
        before = copy.deepcopy(self.package)
        self.assertEqual(self.resolve('lower-door')['material'], 'BLACK_PROFILE')
        self.assertEqual(self.resolve('upper-door')['material'], 'WHITE_MATTE')
        self.assertEqual(self.resolve('lower-door')['scope_id'], 'lower')
        self.assertEqual(self.package, before)

    def test_targets_and_covers_follow_module_family(self):
        self.config['module_finishes']['role_families']['FILLER'] = 'CARCASS'
        self.assertEqual(self.resolve('filler')['material'], 'BLACK_PROFILE')
        self.assertEqual(self.resolve('filler')['family'], 'FRONT')
        self.assertEqual(self.resolve('cover')['material'], 'WHITE_MATTE')
        self.nodes[5]['finish_target'] = 'CARCASS'
        self.assertEqual(self.resolve('filler')['material'], 'WHITE_MATTE')

    def test_piece_exception_wins_and_clearing_restores_inheritance(self):
        self.config['instance_assignments']['lower-door'] = 'LIGHT_COUNTERTOP'
        self.config['definition_assignments']['shared-door'] = 'WHITE_MATTE'
        self.assertEqual(self.resolve('lower-door')['source'], 'instance')
        self.assertEqual(self.resolve('lower-door')['material'], 'LIGHT_COUNTERTOP')
        self.config['instance_assignments'].clear()
        self.assertEqual(self.resolve('lower-door')['source'], 'definition')
        self.config['definition_assignments'].clear()
        self.assertEqual(self.resolve('lower-door')['material'], 'BLACK_PROFILE')

    def test_nearest_module_then_instance_before_definition(self):
        self.nodes.append(node('nested', 'lower'))
        self.nodes[3]['parent_instance_id'] = 'nested'
        self.config['module_finishes']['definitions']['d_nested'] = {'FRONT': 'WHITE_MATTE'}
        self.assertEqual(self.resolve('lower-door')['material'], 'WHITE_MATTE')
        self.assertEqual(self.resolve('lower-door')['source'], 'module_definition')
        self.config['module_finishes']['instances']['nested'] = {'FRONT': 'LIGHT_COUNTERTOP'}
        self.assertEqual(self.resolve('lower-door')['material'], 'LIGHT_COUNTERTOP')
        self.assertEqual(self.resolve('lower-door')['scope_id'], 'nested')

    def test_family_changes_do_not_change_inside_or_gola(self):
        self.config['module_finishes']['instances']['lower']['FRONT'] = 'LIGHT_COUNTERTOP'
        self.assertEqual(self.resolve('lower-door')['material'], 'LIGHT_COUNTERTOP')
        self.assertEqual(self.resolve('inside')['material'], 'WHITE_MATTE')
        self.assertEqual(self.resolve('gola')['material'], 'BLACK_PROFILE')
        self.assertEqual(self.resolve('gola')['source'], 'project_family')

    def test_family_inherits_independently_through_empty_modules(self):
        self.nodes.append(node('nested', 'lower'))
        self.nodes[3]['parent_instance_id'] = 'nested'
        self.config['module_finishes']['instances']['nested'] = {'CARCASS': 'LIGHT_COUNTERTOP'}
        self.assertEqual(self.resolve('lower-door')['material'], 'BLACK_PROFILE')
        self.assertEqual(self.resolve('lower-door')['scope_id'], 'lower')

    def test_stale_snapshot_and_selectors_fail(self):
        self.config['module_finishes']['source_export_id'] = 'snapshot-B'
        with self.assertRaisesRegex(ValueError, 'different source export'):
            self.resolver()
        self.config['module_finishes']['source_export_id'] = 'snapshot-A'
        for kind in ('instances', 'definitions'):
            with self.subTest(kind=kind):
                self.config['module_finishes'][kind]['stale'] = {'FRONT': 'WHITE_MATTE'}
                with self.assertRaisesRegex(ValueError, 'Unknown module'):
                    self.resolver()
                del self.config['module_finishes'][kind]['stale']
        self.config['instance_assignments']['another-export-id'] = 'WHITE_MATTE'
        with self.assertRaisesRegex(ValueError, 'Unknown piece override'):
            self.resolver()

    def test_cycles_missing_parents_and_duplicate_ids_fail(self):
        self.nodes[0]['parent_instance_id'] = 'lower-door'
        with self.assertRaisesRegex(ValueError, 'cycle'):
            self.resolver()
        self.nodes[0]['parent_instance_id'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'Missing module parent'):
            self.resolver()
        self.nodes[0]['parent_instance_id'] = None
        self.nodes.append(copy.deepcopy(self.nodes[3]))
        with self.assertRaisesRegex(ValueError, 'Duplicate instance'):
            self.resolver()

    def test_invalid_family_material_or_options_rejected(self):
        original = copy.deepcopy(self.config['module_finishes'])
        for slots in ({'UNKNOWN': 'WHITE_MATTE'}, {'FRONT': 'missing'}, {'FRONT': None}):
            self.config['module_finishes'] = copy.deepcopy(original)
            self.config['module_finishes']['project'] = slots
            with self.assertRaises(ValueError):
                self.resolver()
        self.config['module_finishes'] = original
        self.config['module_finishes']['execute_python'] = 'bad'
        with self.assertRaises(ValueError):
            self.resolver()

    def test_legacy_presets_need_no_snapshot_or_hierarchy(self):
        for preset in (ROOT / 'presets').glob('*.json'):
            config = preview.validate_config(json.loads(preset.read_text()))
            self.assertIsNone(preview.build_module_resolver(config, {}))

    def test_unknown_target_stays_diagnostic(self):
        self.nodes[3]['finish_target'] = 'UNKNOWN'
        self.assertEqual(self.resolve('lower-door')['source'], 'diagnostic_fallback')

    def test_instance_payload_cannot_be_substituted(self):
        changed = dict(self.nodes[3], role='COVER_PANEL')
        with self.assertRaisesRegex(ValueError, 'does not belong'):
            self.resolver().resolve(changed)

    def test_global_role_assignment_remains_explicit_fallback(self):
        self.config['module_finishes']['instances'].clear()
        resolution = self.resolve('lower-door')
        self.assertEqual(resolution['source'], 'role')
        self.assertEqual(resolution['material'], 'WHITE_MATTE')


if __name__ == '__main__':
    unittest.main()
