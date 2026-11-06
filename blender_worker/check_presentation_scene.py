"""Run in Blender on a saved preview to check isolation from startup objects."""
import argparse
import json
from pathlib import Path
import sys

import bpy


def check_scene():
    scene = bpy.context.scene
    sources = [c for c in scene.collection.children if c.get('kfs_export_id')]
    if len(sources) != 1:
        raise AssertionError('Expected exactly one source collection')
    export_id = sources[0]['kfs_export_id']
    allowed = set()
    for collection in scene.collection.children:
        if (collection.get('kfs_export_id') == export_id
                or collection.get('kfs_preview_export_id') == export_id
                or collection.get('kfs_decor_export_id') == export_id):
            allowed.update(collection.all_objects)
        else:
            raise AssertionError('Unexpected presentation collection: ' + collection.name)
    if set(scene.objects) != allowed:
        raise AssertionError('Unexpected objects in presentation scene')
    if scene.camera not in allowed:
        raise AssertionError('Presentation camera is outside owned setup')
    return {'status': 'PASS', 'source_export_id': export_id,
            'scene': scene.name, 'allowed_objects': len(allowed),
            'objects_retained_outside_scene': [o.name for o in bpy.data.objects if o not in allowed]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    Path(args.report).write_text(json.dumps(check_scene(), indent=2), encoding='utf-8')
