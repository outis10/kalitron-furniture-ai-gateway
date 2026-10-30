"""Pure presentation configuration validation and explicit assignment resolution."""
import math
import importlib.util
from pathlib import Path

_decor_spec=importlib.util.spec_from_file_location('kfs_decor_config',Path(__file__).with_name('decor_plan.py'))
_decor_module=importlib.util.module_from_spec(_decor_spec)
_decor_spec.loader.exec_module(_decor_module)


def validate_config(config):
    """Validate the small preview contract before any Blender scene changes."""
    allowed={'schema_version','label','illustrative','materials','role_assignments',
             'definition_assignments','instance_assignments','fallback_material',
             'floor_material','render','camera','lighting','decor'}
    if set(config)-allowed or config.get('schema_version')!='kfs-preview/0.1' or config.get('illustrative') is not True:
        raise ValueError('Unknown keys/profile or missing illustrative=true')
    materials=config['materials']
    if not materials or not isinstance(materials,dict):
        raise ValueError('Material library is empty')
    for name, material in materials.items():
        if set(material)-{'color','roughness','metallic'}:
            raise ValueError('Unsupported material options: '+name)
        color=material['color']
        if len(color)!=3 or any(not math.isfinite(x) or not 0<=x<=1 for x in color):
            raise ValueError('Invalid RGB color: '+name)
        for key,default in [('roughness',0.5),('metallic',0.0)]:
            value=material.get(key,default)
            if not math.isfinite(value) or not 0<=value<=1:
                raise ValueError('Invalid material value: '+name)
    for key in ('role_assignments','definition_assignments','instance_assignments'):
        for selector, material in config.get(key,{}).items():
            if not isinstance(selector,str) or not selector or material not in materials:
                raise ValueError('Invalid assignment: '+key)
    for key in ('fallback_material','floor_material'):
        if config[key] not in materials:
            raise ValueError('Unknown '+key)
    render=config['render']
    if set(render)-{'width','height','samples','seed'}:
        raise ValueError('Unknown render option')
    for key,low,high in [('width',256,4096),('height',256,4096),('samples',1,256),('seed',0,2147483647)]:
        if type(render[key]) is not int or not low<=render[key]<=high:
            raise ValueError('Invalid render '+key)
    camera=config['camera']
    if set(camera)!={'eye_height_m','target_height_m','lens_mm'}:
        raise ValueError('Unknown camera option')
    for key,low,high in [('eye_height_m',1,2.2),('target_height_m',0.5,1.8),('lens_mm',24,70)]:
        if not math.isfinite(camera[key]) or not low<=camera[key]<=high:
            raise ValueError('Invalid camera '+key)
    lighting=config['lighting']
    if set(lighting)!={'world_strength','key_watts','fill_watts','top_watts'}:
        raise ValueError('Unknown lighting option')
    for key,value in lighting.items():
        if not math.isfinite(value) or not 0<=value<=(5 if key=='world_strength' else 5000):
            raise ValueError('Invalid lighting '+key)
    _decor_module.validate_decor(config.get('decor',[]))
    return config


def resolve_material(config, instance):
    """Resolve operator-configured instance > definition > role > diagnostic fallback."""
    for source,field in [('instance','instance_id'),('definition','definition_id'),('role','role')]:
        assignments=config.get(source+'_assignments',{})
        if instance.get(field) in assignments:
            return assignments[instance[field]], source
    return config['fallback_material'],'diagnostic_fallback'
