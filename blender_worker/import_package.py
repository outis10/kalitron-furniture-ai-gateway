"""E17 diagnostic importer. Run with Blender --background --python ... -- ... ."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys


def bounds(points):
    """Return finite nonempty point bounds."""
    points = list(points)
    if not points or any(len(p) != 3 or not all(math.isfinite(x) for x in p) for p in points):
        raise ValueError('Invalid or empty coordinates')
    return {'min': [min(p[i] for p in points) for i in range(3)],
            'max': [max(p[i] for p in points) for i in range(3)]}


def transform(matrix, vertex):
    """Apply a row-major column-vector affine matrix."""
    return [sum(matrix[r*4+c]*vertex[c] for c in range(3))+matrix[r*4+3] for r in range(3)]


def determinant(m):
    """Find reflection sign of a placement."""
    return m[0]*(m[5]*m[10]-m[6]*m[9])-m[1]*(m[4]*m[10]-m[6]*m[8])+m[2]*(m[4]*m[9]-m[5]*m[8])


def check_bounds(actual, expected, tolerance=1e-5):
    """Reject inconsistent mesh/manifest bounds, in millimeters."""
    for key in ('min', 'max'):
        if len(expected[key]) != 3 or any(not math.isfinite(x) for x in expected[key]):
            raise ValueError('Invalid declared bounds')
        if any(abs(actual[key][i]-expected[key][i]) > tolerance for i in range(3)):
            raise ValueError('Mesh/manifest bounds mismatch')


def read_obj(path):
    """Read the pilot's strict triangle OBJ subset without axis conversion."""
    vertices, faces = [], []
    for line in path.read_text(encoding='utf-8').splitlines():
        fields = line.split()
        if not fields or fields[0].startswith('#') or fields[0] == 'o':
            continue
        if fields[0] == 'v' and len(fields) == 4:
            vertices.append([float(value) for value in fields[1:]])
        elif fields[0] == 'f' and len(fields) == 4:
            faces.append([int(value)-1 for value in fields[1:]])
        else:
            raise ValueError('Unsupported OBJ record')
    bounds(vertices)
    if not faces or any(i < 0 or i >= len(vertices) for face in faces for i in face):
        raise ValueError('Invalid OBJ indices')
    return vertices, faces


def load_package(directory):
    """Validate all package inputs before touching the Blender scene."""
    directory = Path(directory).resolve()
    data = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if data.get('schema_version') != 'kfs-render/1.0' or data.get('profile') != 'diagnostic-pilot/0.1':
        raise ValueError('Unsupported package profile')
    coordinates = data['coordinates']
    if any(coordinates.get(k) != v for k, v in {'units':'mm', 'up_axis':'Z', 'handedness':'right', 'matrix_layout':'row-major', 'vector_convention':'column'}.items()):
        raise ValueError('Unsupported coordinates')
    if data['validation']['final_ready'] is not False or data['validation']['status'] != 'DIAGNOSTIC':
        raise ValueError('Pilot only accepts diagnostic packages')
    definitions, payloads, body_ids = {}, {}, set()
    for definition in data['components']:
        identifier = definition['definition_id']
        if identifier in definitions:
            raise ValueError('Duplicate definition ID')
        definitions[identifier] = definition
        for geometry in definition['geometry_refs']:
            if geometry['body_id'] in body_ids:
                raise ValueError('Duplicate body ID')
            body_ids.add(geometry['body_id'])
            reference = geometry['path']
            path = (directory/reference).resolve()
            if path == directory or directory not in path.parents or Path(reference).is_absolute():
                raise ValueError('Unsafe geometry reference')
            if reference in payloads:
                raise ValueError('Duplicate geometry reference')
            if hashlib.sha256(path.read_bytes()).hexdigest() != geometry['sha256']:
                raise ValueError('Geometry checksum mismatch')
            vertices, faces = read_obj(path)
            if len(vertices) != geometry['vertex_count'] or len(faces) != geometry['triangle_count']:
                raise ValueError('Mesh count mismatch')
            check_bounds(bounds(vertices), geometry['local_bounds_mm'])
            payloads[reference] = (vertices, faces, geometry)
    seen, boxes = set(), []
    for instance in data['instances']:
        identifier = instance['instance_id']
        if identifier in seen:
            raise ValueError('Duplicate instance ID')
        parent = instance['parent_instance_id']
        if parent is not None and parent not in seen:
            raise ValueError('Parent must precede child')
        seen.add(identifier)
        definition = definitions[instance['definition_id']]
        expected_refs = [g['path'] for g in definition['geometry_refs']]
        if instance['geometry_refs'] != expected_refs:
            raise ValueError('Instance geometry ownership mismatch')
        matrix = instance['local_to_world_mm']
        if (len(matrix) != 16 or not all(math.isfinite(v) for v in matrix)
                or any(abs(matrix[12+i]-v)>1e-9 for i,v in enumerate((0,0,0,1)))
                or abs(determinant(matrix)) < 1e-12):
            raise ValueError('Invalid placement matrix')
        if expected_refs:
            if set(instance['body_visibility']) != set(expected_refs) or any(type(v) is not bool for v in instance['body_visibility'].values()):
                raise ValueError('Invalid body visibility mapping')
            local = bounds(p for ref in expected_refs for p in payloads[ref][0])
            check_bounds(local, instance['local_bounds_mm'])
            world = bounds(transform(matrix, p) for p in itertools.product(
                *[(local['min'][i],local['max'][i]) for i in range(3)]))
            check_bounds(world, instance['world_bounds_mm'])
            boxes.append(world)
    if not boxes:
        raise ValueError('Package has no geometry')
    check_bounds(bounds(p for box in boxes for p in (box['min'],box['max'])), data['world_bounds_mm'])
    return data, payloads


def import_package(directory, output):
    """Import into a staging collection, validate, then replace package-owned data."""
    data, payloads = load_package(directory)
    output = Path(output)
    if output.exists():
        raise FileExistsError('Choose a fresh output directory: ' + str(output))
    import bpy
    from mathutils import Matrix
    collection = bpy.data.collections.new('KFS staging')
    bpy.context.scene.collection.children.link(collection)
    created_meshes = []
    imported, errors = [], []
    try:
        for instance in data['instances']:
            matrix_mm = instance['local_to_world_mm']
            matrix = Matrix([matrix_mm[i:i+4] for i in range(0,16,4)])
            for i in range(3):
                matrix[i][3] *= 0.001
            for reference in instance['geometry_refs']:
                vertices, faces, geometry = payloads[reference]
                mesh = bpy.data.meshes.new(geometry['body_id'])
                created_meshes.append(mesh)
                # Bake placement in the worker exactly once; reverse winding for
                # reflected geometry. Preserve local coordinates/matrix as metadata.
                mesh.from_pydata([[v*0.001 for v in p] for p in vertices], [], faces)
                mesh.transform(matrix)
                if determinant(matrix_mm) < 0:
                    mesh.flip_normals()
                mesh.update()
                obj = bpy.data.objects.new(instance['display_name']+' / '+geometry['display_name'], mesh)
                collection.objects.link(obj)
                obj['kfs_instance_id'] = instance['instance_id']
                obj['kfs_definition_id'] = instance['definition_id']
                obj['kfs_body_id'] = geometry['body_id']
                obj['kfs_role'] = instance['role'] or 'UNRESOLVED'
                obj['kfs_finish_id'] = instance['effective_finish_id'] or 'UNRESOLVED'
                obj['kfs_local_to_world_mm'] = matrix_mm
                obj['kfs_diagnostic_placeholder'] = True
                obj.hide_render = not (instance['render_enabled'] and instance['body_visibility'][reference])
                obj.hide_viewport = obj.hide_render
                actual = bounds([[v.co[i]*1000 for i in range(3)] for v in mesh.vertices])
                expected = bounds(transform(matrix_mm,p) for p in vertices)
                check_bounds(actual, expected, tolerance=1.0)
                imported.append(obj.name)
        if not imported:
            raise ValueError('No imported bodies')
    except Exception:
        for obj in list(collection.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)
        for mesh in created_meshes:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        raise
    # Snapshot IDs intentionally cannot match revisions. Replace by project-owned
    # collection only; decorations and other projects remain intact.
    for old in list(bpy.data.collections):
        if old != collection and old.get('kfs_project_id') == data['project_id']:
            for obj in list(old.objects):
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh and mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            bpy.data.collections.remove(old)
    collection.name = 'KFS diagnostic'
    collection['kfs_project_id'] = data['project_id']
    collection['kfs_export_id'] = data['export_id']
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1.0
    output.mkdir(parents=True, exist_ok=False)
    report = {'status':'DIAGNOSTIC_IMPORTED', 'final_ready':False,
              'export_id':data['export_id'], 'blender_version':bpy.app.version_string,
              'imported_body_instances':len(imported), 'dimension_tolerance_mm':1.0,
              'source_issues':data['validation']['issues'], 'errors':errors}
    bpy.ops.wm.save_as_mainfile(filepath=str((output/'diagnostic.blend').resolve()))
    (output/'import-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def main():
    """CLI entry point; Blender flags precede the -- delimiter."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:])
    print(json.dumps(import_package(args.package,args.output), indent=2))


if __name__ == '__main__':
    main()
