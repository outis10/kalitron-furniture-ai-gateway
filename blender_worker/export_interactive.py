"""Export a prepared preview blend to local interactive GLBs without changing source."""
import argparse
import json
from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_preview import geometry_digest


def export_interactive(output, package=None, config=None):
    if (package is None) != (config is None):
        raise ValueError('package and config must be supplied together')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    collections = [c for c in bpy.data.collections if c.get('kfs_export_id')]
    if len(collections) != 1:
        raise ValueError('Expected exactly one imported KFS project')
    export_id = collections[0]['kfs_export_id']
    source = [o for o in collections[0].all_objects if o.get('kfs_instance_id')]
    if not source:
        raise ValueError('Open an imported, material-assigned KFS preview first')
    if any(not o.get('kfs_preview_finish') for o in source):
        raise ValueError('Source objects have no preview material assignment')
    before = geometry_digest(source)
    selection = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    visible = [o for o in source if not o.hide_render and not o.hide_viewport]
    decor = [o for c in bpy.data.collections if c.get('kfs_decor_export_id') == export_id
             for o in c.objects if o.type == 'MESH' and not o.hide_render]
    report = {'schema_version': 'kfs-interactive/0.1', 'status': 'RUNNING',
              'illustrative': True, 'final_ready': False, 'units': 'm',
              'source_export_id': export_id,
              'up_axis': 'Y', 'source_body_count': len(source),
              'visible_source_count': len(visible), 'accessory_mesh_count': len(decor),
              'limitations': ['Browser lighting differs from Cycles.',
                             'Procedural textures and bevel shading are not baked.'],
              'variants': []}
    try:
        for name, objects in [('kitchen', visible + decor),
                              ('kitchen-no-walls', [o for o in visible if o.get('kfs_role') != 'WALL'] + decor)]:
            bpy.ops.object.select_all(action='DESELECT')
            for obj in objects:
                obj.select_set(True)
            path = output / (name + '.glb')
            result = bpy.ops.export_scene.gltf(
                filepath=str(path), export_format='GLB', use_selection=True,
                export_yup=True, export_extras=True, export_animations=False,
                export_cameras=False, export_lights=False, export_apply=False)
            if 'FINISHED' not in result:
                raise RuntimeError('glTF export failed')
            if package is not None:
                from import_package import load_package
                from editable_glb import attach_editor
                data, _ = load_package(package)
                if data['export_id'] != export_id:
                    raise ValueError('Editor package does not match scene')
                attach_editor(path, data, json.loads(Path(config).read_text(encoding='utf-8')))
            report['variants'].append({'file': path.name, 'mesh_objects': len(objects),
                                       'bytes': path.stat().st_size})
        report['source_geometry_unchanged'] = geometry_digest(source) == before
        if not report['source_geometry_unchanged']:
            raise RuntimeError('Source geometry changed')
        report['status'] = 'EXPORTED'
    except Exception as error:
        report.update(status='FAILED', error=str(error))
        raise
    finally:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in selection:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = active
        (output / 'export-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--package')
    parser.add_argument('--config')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    export_interactive(args.output, args.package, args.config)
