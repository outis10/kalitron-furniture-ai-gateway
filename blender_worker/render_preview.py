"""Render explicit illustrative presentations without changing source geometry."""
import argparse
from array import array
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0,str(Path(__file__).resolve().parent))
from preview_config import validate_config, resolve_material
from import_package import load_package
from decor_assets import build_decor


def geometry_digest(objects):
    """Hash source mesh coordinates/topology and placement, excluding materials."""
    digest=hashlib.sha256()
    for obj in sorted(objects,key=lambda o:(o['kfs_instance_id'],o['kfs_body_id'])):
        digest.update((obj['kfs_instance_id']+obj['kfs_body_id']).encode())
        for field,count,values in [('co',3*len(obj.data.vertices),obj.data.vertices),
                                    ('vertices',len(obj.data.loops),obj.data.loops)]:
            if field=='co':
                buffer=array('f',[0])*count
                values.foreach_get('co',buffer)
            else:
                buffer=array('i',[0])*count
                values.foreach_get('vertex_index',buffer)
            digest.update(buffer.tobytes())
        digest.update(array('d',[v for row in obj.matrix_world for v in row]).tobytes())
    return digest.hexdigest()


def render_preview(package, config_path, output):
    """Render three illustrative views and report geometry/visibility integrity."""
    import bpy
    from mathutils import Vector
    started=perf_counter()
    config=validate_config(json.loads(Path(config_path).read_text(encoding='utf-8')))
    data,_=load_package(package)
    output=Path(output)
    if output.exists():
        raise FileExistsError('Choose a fresh render output directory')
    objects=[o for o in bpy.data.objects if o.get('kfs_instance_id')]
    if not objects or not any(c.get('kfs_export_id')==data['export_id'] for c in bpy.data.collections):
        raise ValueError('Open the imported .blend for this exact export first')
    instances={i['instance_id']:i for i in data['instances']}
    body_ids={g['path']:g['body_id'] for c in data['components'] for g in c['geometry_refs']}
    expected={(i['instance_id'],body_ids[g]) for i in data['instances'] for g in i['geometry_refs']}
    actual={(o['kfs_instance_id'],o['kfs_body_id']) for o in objects}
    if len(objects)!=len(expected) or actual!=expected:
        raise ValueError('Source piece/body count mismatch')
    for obj in objects:
        if obj['kfs_instance_id'] not in instances:
            raise ValueError('Unexpected source instance')
    before=geometry_digest(objects)
    original_visibility={o.name:(o.hide_render,o.hide_viewport) for o in objects}
    output.mkdir(parents=True,exist_ok=False)
    (output/'config.json').write_text(json.dumps(config,indent=2,ensure_ascii=False),encoding='utf-8')
    report={'status':'RUNNING','final_ready':False,'illustrative':True,
            'label':config['label'],'source_export_id':data['export_id'],
            'engine':'CYCLES','samples':config['render']['samples'],
            'resolution':[config['render']['width'],config['render']['height']],
            'blender_version':bpy.app.version_string,'source_body_count':len(objects),
            'source_issues':data['validation']['issues'],'material_assignments':[], 'views':[]}

    def write_report():
        (output/'render-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')

    write_report()
    try:
        owned=bpy.data.collections.new('KFS preview setup')
        bpy.context.scene.collection.children.link(owned)
        owned['kfs_preview_export_id']=data['export_id']
        materials={}
        for name,settings in config['materials'].items():
            material=bpy.data.materials.new('KFS '+name)
            material.use_nodes=True
            material.diffuse_color=(*settings['color'],1)
            bsdf=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
            bsdf.inputs['Base Color'].default_value=(*settings['color'],1)
            bsdf.inputs['Roughness'].default_value=settings.get('roughness',0.5)
            bsdf.inputs['Metallic'].default_value=settings.get('metallic',0)
            bevel=material.node_tree.nodes.new('ShaderNodeBevel')
            bevel.inputs['Radius'].default_value=0.0004
            material.node_tree.links.new(bevel.outputs['Normal'],bsdf.inputs['Normal'])
            materials[name]=material
        for obj in objects:
            instance=instances[obj['kfs_instance_id']]
            finish,source=resolve_material(config,instance)
            obj.data.materials.clear()
            obj.data.materials.append(materials[finish])
            obj['kfs_preview_finish']=finish
            obj['kfs_preview_assignment_source']=source
            report['material_assignments'].append({'instance_id':instance['instance_id'],
                    'body_id':obj['kfs_body_id'],'material':finish,'source':source})
        report['fallback_body_count']=sum(a['source']=='diagnostic_fallback' for a in report['material_assignments'])
        report['decor']=build_decor(config.get('decor',[]),objects,data['export_id'])
        visible=[o for o in objects if not o.hide_render]
        points=[o.matrix_world@v.co for o in visible for v in o.data.vertices]
        low=Vector([min(p[i] for p in points) for i in range(3)])
        high=Vector([max(p[i] for p in points) for i in range(3)])
        center=(low+high)*0.5
        target=Vector((center.x,center.y,config['camera']['target_height_m']))
        span=max(high.x-low.x,high.y-low.y,2.0)
        # Separate, explicitly added presentation floor; source meshes stay intact.
        floor=bpy.data.meshes.new('KFS presentation floor')
        floor.from_pydata([(low.x-2,low.y-2,-0.006),(high.x+2,low.y-2,-0.006),
                           (high.x+2,high.y+2,-0.006),(low.x-2,high.y+2,-0.006)],[],[(0,1,2,3)])
        floor.materials.append(materials[config['floor_material']])
        floor_obj=bpy.data.objects.new('KFS presentation floor',floor)
        owned.objects.link(floor_obj)
        floor_obj['kfs_added_presentation_object']=True
        scene=bpy.context.scene
        scene.world=bpy.data.worlds.new('KFS neutral world')
        scene.world.use_nodes=True
        background=scene.world.node_tree.nodes.get('Background')
        background.inputs['Color'].default_value=(0.82,0.86,0.95,1)
        background.inputs['Strength'].default_value=config['lighting']['world_strength']
        lights=[('Key',(center.x+1,low.y-2.5,3.2),'key_watts',3.5),
                ('Fill',(high.x+1,center.y,2.8),'fill_watts',3.0),
                ('Top',(center.x,center.y,3.6),'top_watts',2.5)]
        for name,position,power,size in lights:
            light=bpy.data.lights.new('KFS '+name,'AREA')
            light.energy=config['lighting'][power]
            light.shape='DISK'
            light.size=size
            obj=bpy.data.objects.new('KFS '+name,light)
            owned.objects.link(obj)
            obj.location=position
            obj.rotation_euler=(target-obj.location).to_track_quat('-Z','Y').to_euler()
        camera_data=bpy.data.cameras.new('KFS presentation camera')
        camera=bpy.data.objects.new('KFS presentation camera',camera_data)
        owned.objects.link(camera)
        camera_data.lens=config['camera']['lens_mm']
        camera_data.clip_end=1000
        scene.camera=camera
        scene.render.engine='CYCLES'
        scene.cycles.samples=config['render']['samples']
        scene.cycles.use_denoising=True
        scene.cycles.seed=config['render']['seed']
        scene.cycles.max_bounces=6
        scene.cycles.diffuse_bounces=4
        scene.cycles.glossy_bounces=4
        report['device']='CPU'
        preferences=bpy.context.preferences.addons['cycles'].preferences
        for backend in ('OPTIX','CUDA'):
            try:
                preferences.compute_device_type=backend
                preferences.get_devices()
                devices=[device for device in preferences.devices if device.type==backend]
                if devices:
                    for device in preferences.devices:
                        device.use=device.type==backend
                    scene.cycles.device='GPU'
                    report['device']=backend+': '+', '.join(d.name for d in devices)
                    break
            except (TypeError,RuntimeError):
                continue
        scene.render.resolution_x=config['render']['width']
        scene.render.resolution_y=config['render']['height']
        scene.render.resolution_percentage=100
        scene.render.image_settings.file_format='PNG'
        scene.render.film_transparent=False
        scene.view_settings.view_transform='AgX'
        scene.view_settings.exposure=0
        eye=config['camera']['eye_height_m']
        views=[('perspectiva',(center.x+span*1.25,center.y-span*1.65,eye),False),
               ('frontal',(center.x,low.y-span*1.8,eye),False),
               ('interior',(center.x+span*1.25,center.y-span*1.65,eye),True)]
        for view,position,hide_doors in views:
            hidden=[]
            for obj in objects:
                obj.hide_render=original_visibility[obj.name][0]
                if hide_doors and obj['kfs_role']=='DOOR' and not obj.hide_render:
                    obj.hide_render=True
                    hidden.append(obj['kfs_instance_id'])
            camera.location=position
            camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            scene.render.filepath=str((output/(view+'.png')).resolve())
            report['active_view']=view
            write_report()
            begin=perf_counter()
            last_stats=[0.0]

            def render_stats(message):
                now=perf_counter()
                if now-last_stats[0]>2:
                    report['render_progress']=str(message)
                    write_report()
                    last_stats[0]=now

            bpy.app.handlers.render_stats.append(render_stats)
            try:
                bpy.ops.render.render(write_still=True)
            finally:
                bpy.app.handlers.render_stats.remove(render_stats)
            report['views'].append({'name':view,'file':view+'.png','seconds':round(perf_counter()-begin,2),
                                   'hidden_door_instances':sorted(set(hidden)),
                                   'camera_position_m':list(camera.location),'target_m':list(target)})
            write_report()
        for obj in objects:
            obj.hide_render,obj.hide_viewport=original_visibility[obj.name]
        camera.location=views[0][1]
        camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        after=geometry_digest(objects)
        if before!=after:
            raise RuntimeError('Source geometry or transforms changed during presentation')
        report.update(status='PREVIEW_COMPLETE',geometry_unchanged=True,
                      geometry_sha256=before,source_visibility_restored=True,
                      duration_seconds=round(perf_counter()-started,2),
                      completed_at=datetime.now(timezone.utc).isoformat())
        report.pop('active_view',None)
        report.pop('render_progress',None)
        scene['kfs_illustrative_preview']=True
        scene['kfs_preview_label']=config['label']
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='VIEW_3D':
                    region=area.spaces.active.region_3d
                    region.view_location=target
                    region.view_rotation=camera.rotation_euler.to_quaternion()
                    region.view_distance=(target-camera.location).length
        bpy.ops.wm.save_as_mainfile(filepath=str((output/'presentacion.blend').resolve()))
        write_report()
        return report
    except Exception as error:
        for obj in objects:
            obj.hide_render,obj.hide_viewport=original_visibility[obj.name]
        report.update(status='FAILED',error=str(error),final_ready=False)
        write_report()
        raise


def main():
    """Run with an imported .blend and explicit package/config/output arguments."""
    parser=argparse.ArgumentParser()
    parser.add_argument('--package',required=True)
    parser.add_argument('--config',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:])
    render_preview(args.package,args.config,args.output)


if __name__=='__main__':
    main()
