"""Blender runtime roundtrip check of GLB source identity, scale and coordinates."""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils.kdtree import KDTree


def check(path):
    originals = {}
    for obj in bpy.context.scene.objects:
        if not obj.get('kfs_instance_id') or obj.hide_render or obj.hide_viewport:
            continue
        key = (obj['kfs_instance_id'], obj['kfs_body_id'])
        points = [obj.matrix_world @ v.co for v in obj.data.vertices]
        tree = KDTree(len(points))
        for i, point in enumerate(points):
            tree.insert(point, i)
        tree.balance()
        originals[key] = (tree, obj['kfs_preview_finish'])
    # Use a temporary empty scene; the source .blend is never saved.
    scene = bpy.data.scenes.new('GLB roundtrip check')
    bpy.context.window.scene = scene
    bpy.ops.import_scene.gltf(filepath=str(path))
    seen, max_error = set(), 0.0
    for obj in scene.objects:
        if not obj.get('kfs_instance_id'):
            continue
        key = (obj['kfs_instance_id'], obj['kfs_body_id'])
        tree, finish = originals[key]
        assert obj['kfs_preview_finish'] == finish, 'Material identity changed'
        assert obj.data.materials and finish in obj.data.materials[0].name, 'Material lost'
        for vertex in obj.data.vertices:
            _, _, distance = tree.find(obj.matrix_world @ vertex.co)
            max_error = max(max_error, distance)
        seen.add(key)
    assert seen == set(originals), 'Visible source body set changed'
    assert max_error <= 0.00001, 'GLB geometry/axis/scale mismatch'
    report = {'status': 'PASS', 'source_body_checks': len(seen),
              'maximum_coordinate_error_mm': max_error * 1000,
              'material_identity_preserved': True}
    path.with_name('roundtrip-report.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--glb', required=True)
    check(Path(parser.parse_args(sys.argv[sys.argv.index('--') + 1:]).glb))
