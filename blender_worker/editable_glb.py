"""Attach a self-contained, snapshot-bound finish editor without changing GLB geometry."""
import json
from pathlib import Path
import struct


def read_glb(data):
    if len(data) < 20 or struct.unpack_from('<III', data) != (0x46546C67, 2, len(data)):
        raise ValueError('Invalid GLB header')
    chunks, offset = [], 12
    while offset < len(data):
        if offset + 8 > len(data):
            raise ValueError('Truncated GLB chunk')
        size, kind = struct.unpack_from('<II', data, offset)
        offset += 8
        if size % 4 or offset + size > len(data):
            raise ValueError('Invalid GLB chunk size')
        chunks.append((kind, data[offset:offset + size]))
        offset += size
    if not chunks or chunks[0][0] != 0x4E4F534A or sum(k == 0x4E4F534A for k, _ in chunks) != 1:
        raise ValueError('Expected one leading GLB JSON chunk')
    return json.loads(chunks[0][1]), chunks[1:]


def attach_editor(path, package, config):
    from preview_config import validate_config, build_module_resolver
    validate_config(config)
    resolver = build_module_resolver(config, package)
    if resolver is None or not config['module_finishes'].get('groups'):
        raise ValueError('Editable GLB requires explicit module groups')
    document, binary = read_glb(Path(path).read_bytes())
    instances = resolver.instances
    for node in document.get('nodes', []):
        identifier = node.get('extras', {}).get('kfs_instance_id')
        if identifier and identifier not in instances:
            raise ValueError('GLB contains a different source snapshot')
    labels = {'WHITE_INTERIOR_MATTE': 'Blanco mate', 'WHITE_MATTE': 'Blanco mate',
              'BLACK_MATTE': 'Negro mate', 'BLACK_PROFILE': 'Negro mate',
              'OLIVE_MATTE_PREVIEW': 'Verde olivo mate', 'MINT_PREVIEW': 'Verde menta',
              'WHITE_COUNTERTOP': 'Blanco satinado', 'LIGHT_COUNTERTOP': 'Blanco satinado',
              'PEARL_BEIGE_WALL': 'Perla beige'}
    excluded = {config['fallback_material'], config['floor_material']}
    editor = {'schema_version': 'kfs-finish-editor/0.1',
              'source_export_id': package['export_id'], 'config': config,
              'instances': [{k: i.get(k) for k in ('instance_id', 'definition_id',
                             'parent_instance_id', 'display_name', 'role', 'finish_target')}
                            for i in package['instances']],
              'finish_options': [{'id': key, 'label': labels.get(key, key.replace('_', ' ').title())}
                                 for key in config['materials'] if key not in excluded]}
    document.setdefault('asset', {}).setdefault('extras', {})['kfs_finish_editor'] = editor
    encoded = json.dumps(document, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    encoded += b' ' * (-len(encoded) % 4)
    chunks = [(0x4E4F534A, encoded)] + binary
    payload = b''.join(struct.pack('<II', len(data), kind) + data for kind, data in chunks)
    Path(path).write_bytes(struct.pack('<III', 0x46546C67, 2, len(payload) + 12) + payload)
