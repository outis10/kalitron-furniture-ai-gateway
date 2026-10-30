"""Pure accessory configuration and conservative countertop footprint planning."""
import math
import re

ASSETS={'potted_plant_v1','cutting_board_v1'}


def validate_decor(items):
    """Accept only the versioned library and bounded, millimeter-based options."""
    if not isinstance(items,list) or len(items)>8:
        raise ValueError('Decor must be a list of at most eight props')
    seen=set()
    for item in items:
        if set(item)!={'id','asset','dimensions_mm','rotation_deg','placement'}:
            raise ValueError('Unknown or missing decor option')
        identifier=item['id']
        if not isinstance(identifier,str) or not re.fullmatch(r'[a-zA-Z0-9_]{1,64}',identifier) or identifier in seen:
            raise ValueError('Invalid or duplicate decor ID')
        seen.add(identifier)
        if item['asset'] not in ASSETS or item['placement'] not in ('back_right','front_center'):
            raise ValueError('Unsupported decor asset or placement')
        dims=item['dimensions_mm']
        if not isinstance(dims,list) or len(dims)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in dims):
            raise ValueError('Invalid accessory dimensions')
        limits=([(120,250),(120,250),(200,450)] if item['asset']=='potted_plant_v1'
                else [(200,500),(150,350),(10,35)])
        if any(not low<=value<=high for value,(low,high) in zip(dims,limits)):
            raise ValueError('Accessory dimensions outside library bounds')
        if item['asset']=='potted_plant_v1' and abs(dims[0]-dims[1])>1:
            raise ValueError('Plant footprint must be circular')
        rotation=item['rotation_deg']
        if type(rotation) not in (int,float) or not math.isfinite(rotation) or abs(rotation)>180:
            raise ValueError('Invalid decor rotation')
    return items


def footprint(center, dimensions_mm, rotation_deg):
    """Return four rotated rectangle corners in world meters."""
    angle=math.radians(rotation_deg)
    cosine,sine=math.cos(angle),math.sin(angle)
    half_x,half_y=dimensions_mm[0]/2000,dimensions_mm[1]/2000
    return [[center[0]+cosine*x-sine*y,center[1]+sine*x+cosine*y]
            for x,y in [(-half_x,-half_y),(half_x,-half_y),(half_x,half_y),(-half_x,half_y)]]


def support_samples(corners):
    """Sample center, all corners and edge midpoints; holes fail in Blender."""
    return [[sum(p[i] for p in corners)/4 for i in range(2)]]+corners+[
        [(corners[j][i]+corners[(j+1)%4][i])/2 for i in range(2)] for j in range(4)]


def overlaps(a,b,epsilon=0.001):
    """Conservative box intersection with a one-millimeter touching allowance."""
    return all(min(a['max'][i],b['max'][i])-max(a['min'][i],b['min'][i])>epsilon for i in range(3))


def propose_decor(items,surfaces,clearance_m=0.06):
    """Place on the longest visible countertop, leaving margins and avoiding peers."""
    validate_decor(items)
    if not items:
        return []
    if not surfaces:
        raise ValueError('No visible countertop available for decoration')
    surface=max(surfaces,key=lambda s:(max(s['bounds']['max'][i]-s['bounds']['min'][i] for i in (0,1)),s['key']))
    box=surface['bounds']
    planned=[]
    for item in items:
        origin_corners=footprint((0,0),item['dimensions_mm'],item['rotation_deg'])
        half=[max(abs(p[i]) for p in origin_corners) for i in range(2)]
        if item['placement']=='back_right':
            center=[box['max'][i]-half[i]-clearance_m for i in range(2)]
        else:
            center=[(box['min'][0]+box['max'][0])/2,box['min'][1]+half[1]+clearance_m]
        corners=footprint(center,item['dimensions_mm'],item['rotation_deg'])
        if any(p[i]<box['min'][i]+clearance_m-1e-9 or p[i]>box['max'][i]-clearance_m+1e-9
               for p in corners for i in range(2)):
            raise ValueError('Countertop too small for '+item['id'])
        z=box['max'][2]+0.001
        prop_box={'min':[min(p[0] for p in corners),min(p[1] for p in corners),z],
                  'max':[max(p[0] for p in corners),max(p[1] for p in corners),z+item['dimensions_mm'][2]/1000]}
        if any(overlaps(prop_box,p['bounds_m']) for p in planned):
            raise ValueError('Accessory footprints overlap')
        planned.append(dict(item,anchor_key=surface['key'],position_m=[*center,z],
                            corners_m=corners,bounds_m=prop_box))
    return planned
