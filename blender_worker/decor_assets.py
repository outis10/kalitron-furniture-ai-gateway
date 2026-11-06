"""Original procedural KFS accessories, isolated from imported furniture."""
import math
import random

from decor_plan import propose_decor, support_samples, overlaps


def _box(obj):
    from mathutils import Vector
    points=[obj.matrix_world@Vector(p) for p in obj.bound_box]
    return {'min':[min(p[i] for p in points) for i in range(3)],
            'max':[max(p[i] for p in points) for i in range(3)]}


def _material(name,color,roughness):
    import bpy
    material=bpy.data.materials.new('KFS decor '+name)
    material['kfs_decor_material']=True
    material.use_nodes=True
    shader=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    shader.inputs['Base Color'].default_value=(*color,1)
    shader.inputs['Roughness'].default_value=roughness
    return material


def _mesh(collection,root,name,vertices,faces,material,smooth=False):
    import bpy
    mesh=bpy.data.meshes.new(name)
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    mesh.materials.append(material)
    obj=bpy.data.objects.new(name,mesh)
    collection.objects.link(obj)
    obj.parent=root
    obj['kfs_decor_id']=root['kfs_decor_id']
    obj['kfs_added_presentation_object']=True
    for polygon in mesh.polygons:
        polygon.use_smooth=smooth
    return obj


def _lathe(collection,root,name,profile,material,segments=64):
    vertices=[(r*math.cos(2*math.pi*j/segments),r*math.sin(2*math.pi*j/segments),z)
              for r,z in profile for j in range(segments)]
    faces=[]
    for i in range(len(profile)):
        following=(i+1)%len(profile)
        for j in range(segments):
            faces.append((i*segments+j,i*segments+(j+1)%segments,
                          following*segments+(j+1)%segments,following*segments+j))
    return _mesh(collection,root,name,vertices,faces,material,True)


def _tube(collection,root,name,start,end,radius,material):
    from mathutils import Vector
    a,b=Vector(start),Vector(end)
    axis=(b-a).normalized()
    tangent=axis.cross(Vector((1,0,0)))
    if tangent.length<0.1:
        tangent=axis.cross(Vector((0,1,0)))
    tangent.normalize()
    other=axis.cross(tangent)
    vertices=[]
    segments=10
    for center in (a,b):
        for j in range(segments):
            angle=2*math.pi*j/segments
            vertices.append(tuple(center+radius*(math.cos(angle)*tangent+math.sin(angle)*other)))
    faces=[(j,(j+1)%segments,(j+1)%segments+segments,j+segments) for j in range(segments)]
    faces.extend([tuple(reversed(range(segments))),tuple(range(segments,segments*2))])
    return _mesh(collection,root,name,vertices,faces,material,True)


def _plant(collection,root,dimensions):
    radius=dimensions[0]/2000
    height=dimensions[2]/1000
    pot_h=height*.37
    ceramic=_material('warm ceramic',(0.37,0.23,0.12),0.68)
    soil=_material('soil',(0.025,0.016,0.009),0.97)
    leaf=_material('foliage',(0.028,0.16,0.045),0.4)
    stem=_material('stems',(0.07,0.16,0.025),0.64)
    shader=next(n for n in leaf.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    if shader.inputs.get('Subsurface Weight'):
        shader.inputs['Subsurface Weight'].default_value=0.05
    outer=radius*.78
    # Closed ceramic section: outer shell, rolled lip, inner shell and bottom.
    profile=[(outer*.75,0.002),(outer*.8,0),(outer, pot_h*.94),
             (outer*.99,pot_h),(outer*.91,pot_h),(outer*.9,pot_h*.93),
             (outer*.67,pot_h*.12)]
    _lathe(collection,root,'Ceramic pot',profile,ceramic)
    _lathe(collection,root,'Soil',[(outer*.88,pot_h*.90),(0.0001,pot_h*.90),
                                  (0.0001,pot_h*.87),(outer*.88,pot_h*.87)],soil)
    _tube(collection,root,'Plant main stem',(0,0,pot_h*.89),(0,0,height*.93),0.0014,stem)
    randomizer=random.Random(17)
    vertices,faces=[],[]
    for index in range(18):
        angle=index*2.39996
        base_z=pot_h*.96+(height*.86-pot_h)*(index/18)
        distance=radius*randomizer.uniform(.57,.81)
        width=radius*randomizer.uniform(.23,.34)
        dx,dy=math.cos(angle),math.sin(angle)
        start=(dx*radius*.07,dy*radius*.07,base_z)
        end=(start[0]+dx*distance*.24,start[1]+dy*distance*.24,base_z+distance*.15)
        _tube(collection,root,'Leaf stem '+str(index),start,end,0.00065,stem)
        offset=len(vertices)
        sections,rows=12,5
        for section in range(sections):
            t=.01+.98*section/(sections-1)
            half=math.sin(math.pi*t)**.75*width*.5
            for row in range(rows):
                side=(row/(rows-1)*2-1)
                ridge=(1-abs(side))*width*.12*math.sin(math.pi*t)
                vertices.append((end[0]+dx*distance*t-dy*half*side,
                                 end[1]+dy*distance*t+dx*half*side,
                                 end[2]+distance*(.35*t-.5*t*t)+ridge))
        for section in range(sections-1):
            for row in range(rows-1):
                p=offset+section*rows+row
                faces.append((p,p+rows,p+rows+1,p+1))
    _mesh(collection,root,'Plant leaves',vertices,faces,leaf,True)


def _board(collection,root,dimensions):
    width,depth,height=[v/1000 for v in dimensions]
    wood=_material('cutting board wood',(0.4,0.22,0.09),0.48)
    nodes,links=wood.node_tree.nodes,wood.node_tree.links
    shader=next(n for n in nodes if n.type=='BSDF_PRINCIPLED')
    coords=nodes.new('ShaderNodeTexCoord')
    stretch=nodes.new('ShaderNodeVectorMath')
    stretch.operation='MULTIPLY'
    stretch.inputs[1].default_value=(6,170,20)
    links.new(coords.outputs['Object'],stretch.inputs[0])
    noise=nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value=1
    noise.inputs['Detail'].default_value=3
    links.new(stretch.outputs[0],noise.inputs['Vector'])
    ramp=nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position=.2
    ramp.color_ramp.elements[0].color=(.19,.075,.022,1)
    ramp.color_ramp.elements[1].position=.8
    ramp.color_ramp.elements[1].color=(.52,.29,.11,1)
    links.new(noise.outputs['Fac'],ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'],shader.inputs['Base Color'])
    bump=nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value=.13
    bump.inputs['Distance'].default_value=.00015
    links.new(noise.outputs['Fac'],bump.inputs['Height'])
    links.new(bump.outputs['Normal'],shader.inputs['Normal'])
    radius=min(width,depth)*.1
    bevel=.0015
    vertices=[]
    for inset,z in [(bevel,0),(0,bevel),(0,height-bevel),(bevel,height)]:
        half_x,half_y=width/2-inset,depth/2-inset
        r=radius-inset
        for cx,cy,start in [(half_x-r,half_y-r,0),(-half_x+r,half_y-r,90),
                            (-half_x+r,-half_y+r,180),(half_x-r,-half_y+r,270)]:
            for step in range(9):
                angle=math.radians(start+step*90/8)
                vertices.append((cx+r*math.cos(angle),cy+r*math.sin(angle),z))
    count=36
    faces=[tuple(reversed(range(count))),tuple(range(count*3,count*4))]
    for ring in range(3):
        for j in range(count):
            faces.append((ring*count+j,ring*count+(j+1)%count,
                          (ring+1)*count+(j+1)%count,(ring+1)*count+j))
    _mesh(collection,root,'Rounded cutting board',vertices,faces,wood)


def build_decor(items,source_objects,export_id):
    """Validate source support/clearance, stage accessories, then replace owned decor."""
    import bpy
    from mathutils import Vector
    if not items:
        old=[c for c in bpy.data.collections if c.get('kfs_decor_export_id')==export_id]
        if any(o.get('kfs_instance_id') for c in old for o in c.objects):
            raise ValueError('Decor collection contains source furniture')
        for previous in old:
            _remove_collection(previous)
        return []
    visible=[o for o in source_objects if not o.hide_render]
    surfaces=[{'key':o.name,'bounds':_box(o)} for o in visible if o['kfs_role']=='COUNTERTOP']
    plans=propose_decor(items,surfaces)
    source_by_name={o.name:o for o in visible}
    for plan in plans:
        anchor=source_by_name[plan['anchor_key']]
        inverse=anchor.matrix_world.inverted()
        heights=[]
        for x,y in support_samples(plan['corners_m']):
            origin=inverse@Vector((x,y,plan['position_m'][2]+1))
            direction=(inverse.to_3x3()@Vector((0,0,-1))).normalized()
            hit,point,normal,_=anchor.ray_cast(origin,direction)
            if not hit:
                raise ValueError('Unsupported accessory footprint: '+plan['id'])
            world_point=anchor.matrix_world@point
            world_normal=(inverse.to_3x3().transposed()@normal).normalized()
            if world_normal.z<.95:
                raise ValueError('Accessory needs an upward countertop face')
            heights.append(world_point.z)
        if max(heights)-min(heights)>.002:
            raise ValueError('Accessory support is not flat')
        plan['position_m'][2]=max(heights)+.001
        plan['bounds_m']['min'][2]=plan['position_m'][2]
        plan['bounds_m']['max'][2]=plan['position_m'][2]+plan['dimensions_mm'][2]/1000
        for obj in visible:
            if obj!=anchor and overlaps(plan['bounds_m'],_box(obj),epsilon=.002):
                raise ValueError('Accessory intersects source object: '+plan['id']+' / '+obj.name)
        plan['support_checks']=len(heights)
    old=[c for c in bpy.data.collections if c.get('kfs_decor_export_id')==export_id]
    if any(o.get('kfs_instance_id') for c in old for o in c.objects):
        raise ValueError('Refusing to replace a decor collection containing source furniture')
    collection=bpy.data.collections.new('KFS decor staging')
    bpy.context.scene.collection.children.link(collection)
    try:
        for plan in plans:
            root=bpy.data.objects.new('KFS decor '+plan['id'],None)
            collection.objects.link(root)
            root['kfs_decor_id']=plan['id']
            root['kfs_decor_asset']=plan['asset']
            root['kfs_added_presentation_object']=True
            root.location=plan['position_m']
            root.rotation_euler.z=math.radians(plan['rotation_deg'])
            if plan['asset']=='potted_plant_v1':
                _plant(collection,root,plan['dimensions_mm'])
                points=[v.co for child in root.children if child.type=='MESH' for v in child.data.vertices]
                radius=max(math.hypot(p.x,p.y) for p in points)
                top=max(p.z for p in points)
                xy=plan['dimensions_mm'][0]/2000/radius
                root.scale=(xy,xy,plan['dimensions_mm'][2]/1000/top)
            else:
                _board(collection,root,plan['dimensions_mm'])
            root['kfs_nominal_dimensions_mm']=plan['dimensions_mm']
        bpy.context.view_layer.update()
    except Exception:
        _remove_collection(collection)
        raise
    for previous in old:
        _remove_collection(previous)
    collection.name='KFS accessories'
    collection['kfs_decor_export_id']=export_id
    collection['kfs_decor_library_version']='1'
    return [{'id':p['id'],'asset':p['asset'],'dimensions_mm':p['dimensions_mm'],
             'position_m':p['position_m'],'rotation_deg':p['rotation_deg'],
             'anchor_instance_id':source_by_name[p['anchor_key']]['kfs_instance_id'],
             'anchor_body_id':source_by_name[p['anchor_key']]['kfs_body_id'],
             'support_checks':p['support_checks'],'source_clearance_verified':True}
            for p in plans]


def _remove_collection(collection):
    import bpy
    materials=set()
    for obj in list(collection.objects):
        mesh=obj.data if obj.type=='MESH' else None
        if mesh:
            materials.update(m for m in mesh.materials if m and m.get('kfs_decor_material'))
        bpy.data.objects.remove(obj,do_unlink=True)
        if mesh and mesh.users==0:
            bpy.data.meshes.remove(mesh)
    bpy.data.collections.remove(collection)
    for material in materials:
        if material.users==0:
            bpy.data.materials.remove(material)
