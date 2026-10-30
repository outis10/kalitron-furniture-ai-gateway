"""Placement contracts without Blender: units, clearance, rotations and failures."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('kfs_decor_plan_test',ROOT/'decor_plan.py')
decor=importlib.util.module_from_spec(spec)
spec.loader.exec_module(decor)


class DecorPlanTests(unittest.TestCase):
    def setUp(self):
        self.items=[{'id':'plant_01','asset':'potted_plant_v1','dimensions_mm':[180,180,320],
                     'rotation_deg':0,'placement':'back_right'},
                    {'id':'board_01','asset':'cutting_board_v1','dimensions_mm':[350,240,18],
                     'rotation_deg':-12,'placement':'front_center'}]
        self.surfaces=[{'key':'main','bounds':{'min':[0,-.6,.88],'max':[2.55,0,.892]}},
                       {'key':'bar','bounds':{'min':[0,-2.34,.976],'max':[1.62,-1.79,1]}}]

    def test_place_two_props_on_longest_surface_in_meters(self):
        plans=decor.propose_decor(self.items,self.surfaces)
        self.assertEqual(len(plans),2)
        self.assertTrue(all(p['anchor_key']=='main' for p in plans))
        self.assertAlmostEqual(plans[0]['position_m'][2],.893)
        self.assertAlmostEqual(plans[0]['bounds_m']['max'][2],1.213)
        self.assertFalse(decor.overlaps(plans[0]['bounds_m'],plans[1]['bounds_m']))

    def test_rotated_footprint_retains_clearance(self):
        plans=decor.propose_decor(self.items,self.surfaces)
        for plan in plans:
            for x,y in plan['corners_m']:
                self.assertTrue(.06-1e-8<=x<=2.49+1e-8)
                self.assertTrue(-.54-1e-8<=y<=-.06+1e-8)
        self.assertEqual(len(decor.support_samples(plans[1]['corners_m'])),9)

    def test_empty_is_backwards_compatible(self):
        self.assertEqual(decor.propose_decor([],[]),[])

    def test_missing_surface_fails(self):
        with self.assertRaisesRegex(ValueError,'No visible countertop'):
            decor.propose_decor(self.items,[])

    def test_small_surface_fails_instead_of_overhanging(self):
        with self.assertRaises(ValueError):
            decor.propose_decor(self.items,[{'key':'tiny','bounds':{'min':[0,0,0],'max':[.2,.2,.02]}}])

    def test_duplicate_ids_rejected(self):
        self.items[1]['id']=self.items[0]['id']
        with self.assertRaises(ValueError): decor.validate_decor(self.items)

    def test_unknown_asset_rejected(self):
        self.items[0]['asset']='arbitrary_python'
        with self.assertRaises(ValueError): decor.validate_decor(self.items)

    def test_nonfinite_dimensions_rejected(self):
        self.items[0]['dimensions_mm'][0]=float('nan')
        with self.assertRaises(ValueError): decor.validate_decor(self.items)

    def test_overlapping_props_fail(self):
        duplicate=copy.deepcopy(self.items[0]);duplicate['id']='plant_02'
        with self.assertRaisesRegex(ValueError,'overlap'):
            decor.propose_decor([self.items[0],duplicate],self.surfaces)


if __name__=='__main__':
    unittest.main()
