"""Author the ordered GDD environment pass on the saved gameplay map.

Dispatch only after the three earlier gameplay items have passed. This script
keeps the existing walkable meshes, collisions, navigation, stages and source
material packages. New material graphs and cosmetic instance groups are owned
by this task and applied to main-map components only.
"""
import hashlib
import json
import importlib.util
import math
import shutil
import time
import traceback
from pathlib import Path
import unreal

P = Path(unreal.Paths.project_dir()).resolve()
O = P / 'Docs/Gameplay/GDDOrdered1105'
MAP = '/Game/ReversedScale/Maps/L_NilinGameplayV01'
DEST = '/Game/ReversedScale/Environment/GDD1105'
TAG = 'NL.GDD1105.Art'
FOLDER = 'Nilin_GDD1105_Art'
A = unreal.EditorAssetLibrary
G = unreal.MaterialEditingLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
LEVEL = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
REPORT = {'state': 'starting', 'map': MAP, 'started_utc': time.time(), 'materials': {},
          'material_overrides': [], 'decorations': [], 'backups': []}


def xyz(v): return [float(v.x), float(v.y), float(v.z)]


def transform_value(t):
    q = t.rotation
    return {'p': xyz(t.translation), 's': xyz(t.scale3d), 'q': [q.x, q.y, q.z, q.w]}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def backup_file(path):
    path = path.resolve()
    assert path.is_relative_to(P) and path.is_file(), str(path)
    target = O / 'Backups' / path.relative_to(P)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)
    REPORT['backups'].append({'source': str(path), 'backup': str(target),
                             'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})


def material_file(path):
    return P / 'Content' / (path.removeprefix('/Game/') + '.uasset')


def node(m, cls, **properties):
    n = G.create_material_expression(m, cls)
    assert n
    for key, value in properties.items(): n.set_editor_property(key, value)
    return n


def wire(a, output, b, pin=''):
    assert G.connect_material_expressions(a, output, b, pin), (a.get_name(), output, b.get_name(), pin)


def output(n, prop, pin=''):
    assert G.connect_material_property(n, pin, prop), (n.get_name(), str(prop), pin)


def scalar(m, value): return node(m, unreal.MaterialExpressionConstant, r=float(value))


def color(m, value):
    return node(m, unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(*value, 1))


def op(m, cls, a=None, b=None, **props):
    n = node(m, cls, **props)
    if a is not None: wire(a, '', n, 'A')
    if b is not None: wire(b, '', n, 'B')
    return n


def multiply(m, a, b=None, value=1):
    return op(m, unreal.MaterialExpressionMultiply, a, b, const_b=float(value))


def add(m, a, b=None, value=0):
    return op(m, unreal.MaterialExpressionAdd, a, b, const_b=float(value))


def mask(m, n, channels):
    c = node(m, unreal.MaterialExpressionComponentMask,
             r='r' in channels, g='g' in channels, b='b' in channels, a=False)
    wire(n, '', c)
    return c


def make_material(name, unlit=False, translucent=False):
    assert name.startswith('M_NL1105_')
    path = DEST + '/Materials/' + name
    existing = A.does_asset_exist(path)
    if existing:
        backup_file(material_file(path))
        m = A.load_asset(path)
    else:
        m = TOOLS.create_asset(name, DEST + '/Materials', unreal.Material, unreal.MaterialFactoryNew())
    assert isinstance(m, unreal.Material), path
    for prop in (unreal.MaterialProperty.MP_BASE_COLOR, unreal.MaterialProperty.MP_ROUGHNESS,
                 unreal.MaterialProperty.MP_METALLIC, unreal.MaterialProperty.MP_EMISSIVE_COLOR,
                 unreal.MaterialProperty.MP_OPACITY, unreal.MaterialProperty.MP_NORMAL):
        G.disconnect_material_property(m, prop)
    G.delete_all_material_expressions(m)
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT if translucent else unreal.BlendMode.BLEND_OPAQUE)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT if unlit else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    m.set_editor_property('two_sided', False)
    G.set_base_material_usage(m, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES, True)
    return m


def finish_material(m):
    G.layout_material_expressions(m)
    errors = G.recompile_material(m)
    assert not errors, (m.get_path_name(), list(errors))
    assert G.has_material_usage(m,unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES), m.get_path_name()
    assert A.save_loaded_asset(m, False), m.get_path_name()
    REPORT['materials'][m.get_name()] = m.get_path_name()
    return m


def sample(m, texture, uv, srgb=True):
    sample_type = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
    if not srgb:
        sample_type = (unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
            if texture.get_editor_property('compression_settings') == unreal.TextureCompressionSettings.TC_MASKS
            else unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    t = node(m, unreal.MaterialExpressionTextureSample, texture=texture,
             sampler_type=sample_type)
    # TextureSample's displayed first pin differs between engine branches.
    wire(uv, '', t)
    return t


def world_uv(m, tile_cm, channels='rg'):
    p = node(m, unreal.MaterialExpressionWorldPosition)
    scale = multiply(m, p, value=1.0/tile_cm)
    return mask(m, scale, channels)


def projected_texture(m, texture, tile_cm, srgb=True):
    """Cheap three-sample, sharpened vertex-normal triplanar projection."""
    world = node(m, unreal.MaterialExpressionWorldPosition)
    scaled = multiply(m, world, value=1.0/tile_cm)
    normal = node(m, unreal.MaterialExpressionVertexNormalWS)
    absolute = node(m, unreal.MaterialExpressionAbs); wire(normal, '', absolute)
    power = node(m, unreal.MaterialExpressionPower, const_exponent=4.0); wire(absolute, '', power, 'Base')
    weights = [mask(m, power, channel) for channel in ('r', 'g', 'b')]
    denominator = add(m, add(m, weights[0], weights[1]), weights[2])
    terms = []
    for channels, weight in zip(('gb', 'rb', 'rg'), weights):
        uv = mask(m, scaled, channels)
        tex = sample(m, texture, uv, srgb)
        rgb = mask(m, tex, 'rgb')
        normalized = op(m, unreal.MaterialExpressionDivide, weight, denominator)
        terms.append(multiply(m, rgb, normalized))
    return add(m, add(m, terms[0], terms[1]), terms[2])


def solid_material(name, tint, roughness=.8, metallic=0, emission=0):
    m = make_material(name)
    c = color(m, tint)
    output(c, unreal.MaterialProperty.MP_BASE_COLOR)
    output(scalar(m, roughness), unreal.MaterialProperty.MP_ROUGHNESS)
    output(scalar(m, metallic), unreal.MaterialProperty.MP_METALLIC)
    if emission: output(multiply(m, c, value=emission), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish_material(m)


def textured_material(name, texture, tint, tile_cm, roughness=.85, orm=None, rough_floor=.18, rough_scale=.75, two_sided=False):
    m = make_material(name)
    m.set_editor_property('two_sided',two_sided)
    base = projected_texture(m, texture, tile_cm)
    output(multiply(m, base, color(m, tint)), unreal.MaterialProperty.MP_BASE_COLOR)
    if orm:
        packed = projected_texture(m, orm, tile_cm, False)
        rough = add(m, multiply(m, mask(m, packed, 'g'), value=rough_scale), value=rough_floor)
        output(rough, unreal.MaterialProperty.MP_ROUGHNESS)
        output(multiply(m, mask(m, packed, 'b'), value=.35), unreal.MaterialProperty.MP_METALLIC)
    else:
        output(scalar(m, roughness), unreal.MaterialProperty.MP_ROUGHNESS)
    return finish_material(m)


def floor_material(texture):
    m = make_material('M_NL1105_StoneFloor')
    uv = world_uv(m, 200)
    base_sample = sample(m, texture, world_uv(m, 155))
    grain = multiply(m, mask(m, base_sample, 'rgb'), color(m, (.75, .81, .76)))
    fractions = node(m, unreal.MaterialExpressionFrac); wire(uv, '', fractions)
    u, v = mask(m, fractions, 'r'), mask(m, fractions, 'g')
    inv_u = node(m, unreal.MaterialExpressionOneMinus); wire(u, '', inv_u)
    inv_v = node(m, unreal.MaterialExpressionOneMinus); wire(v, '', inv_v)
    edge_u = op(m, unreal.MaterialExpressionMin, u, inv_u)
    edge_v = op(m, unreal.MaterialExpressionMin, v, inv_v)
    distance = op(m, unreal.MaterialExpressionMin, edge_u, edge_v)
    line = op(m, unreal.MaterialExpressionSubtract, scalar(m, .012), distance)
    alpha = node(m, unreal.MaterialExpressionClamp, min_default=0, max_default=1)
    wire(multiply(m, line, value=1/.012), '', alpha)
    mix = node(m, unreal.MaterialExpressionLinearInterpolate)
    wire(grain, '', mix, 'A'); wire(color(m, (.115, .14, .13)), '', mix, 'B'); wire(alpha, '', mix, 'Alpha')
    output(mix, unreal.MaterialProperty.MP_BASE_COLOR)
    output(scalar(m, .82), unreal.MaterialProperty.MP_ROUGHNESS)
    return finish_material(m)


def cloud_material():
    m = make_material('M_NL1105_CloudSea', unlit=True, translucent=True)
    output(color(m, (.68, .78, .79)), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    fresnel = node(m, unreal.MaterialExpressionFresnel, exponent=1.5, base_reflect_fraction=0)
    center = node(m, unreal.MaterialExpressionOneMinus); wire(fresnel, '', center)
    opacity = multiply(m, center, value=.34)
    fade = node(m, unreal.MaterialExpressionDepthFade, fade_distance_default=600.0)
    wire(opacity, '', fade, 'Opacity')
    output(fade, unreal.MaterialProperty.MP_OPACITY)
    return finish_material(m)


def beacon_material():
    m=make_material('M_NL1105_SealBeacon',unlit=True)
    m.set_editor_property('blend_mode',unreal.BlendMode.BLEND_ADDITIVE)
    face=node(m,unreal.MaterialExpressionFresnel,exponent=2.0,base_reflect_fraction=0)
    center=node(m,unreal.MaterialExpressionOneMinus);wire(face,'',center)
    world=node(m,unreal.MaterialExpressionWorldPosition)
    height=mask(m,world,'b')
    relative=op(m,unreal.MaterialExpressionSubtract,height,scalar(m,17000))
    fade=node(m,unreal.MaterialExpressionClamp,min_default=0,max_default=1)
    wire(multiply(m,relative,value=1/2400),'',fade)
    tip=node(m,unreal.MaterialExpressionOneMinus);wire(fade,'',tip)
    opacity=multiply(m,multiply(m,center,tip),value=.48)
    output(opacity,unreal.MaterialProperty.MP_OPACITY)
    output(color(m,(.38,2.6,2.05)),unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return finish_material(m)


def build_materials():
    tex_root = '/Game/AsianTemple/Environment/Texture/'
    load = lambda path: A.load_asset(tex_root+path)
    rock = load('RockTilable/T_Cliff_01a_D')
    roof = load('Roof_01a/T_Roof_01a_D')
    roof_orm = load('Roof_01a/T_Roof_01a_ORM')
    wood = load('Wood_Red_Desaturated_01a/T_Wood_Red_Desaturated_01a_D')
    wood_orm = load('Wood_Red_Desaturated_01a/T_Wood_Red_Desaturated_01a_ORM')
    assert all(isinstance(t, unreal.Texture2D) for t in (rock, roof, roof_orm, wood, wood_orm))
    mats = {
        'Floor': floor_material(rock),
        'Stone': textured_material('M_NL1105_CarvedStone', rock, (.70, .77, .73), 150),
        'Cliff': textured_material('M_NL1105_MountainRock', rock, (.58, .68, .66), 480, .94),
        'CliffLight': textured_material('M_NL1105_PaleRock', rock, (.76, .82, .75), 320, .94),
        'Roof': textured_material('M_NL1105_JadeRoof', roof, (.34, .58, .58), 280, orm=roof_orm,
                                 rough_floor=.48,rough_scale=.45,two_sided=True),
        'Wood': textured_material('M_NL1105_Redwood', wood, (.44, .29, .24), 230, orm=wood_orm),
        'Trim': solid_material('M_NL1105_AgedGold', (.32, .25, .12), .58, .42),
        'Accent': solid_material('M_NL1105_JadeSeal', (.035, .42, .34), .32, .12, 1.6),
        'Warm': solid_material('M_NL1105_LanternAmber', (1.0, .52, .12), .4, 0, 1.5),
        'Joint': solid_material('M_NL1105_StoneJoint', (.09, .13, .13), .95),
        'Pine': solid_material('M_NL1105_Pine', (.065, .19, .12), .9),
        'Banner': solid_material('M_NL1105_IndigoCloth', (.035, .13, .16), .92),
        'Cloud': cloud_material(),
        'Far': textured_material('M_NL1105_DistantJadeRock', rock, (.39, .57, .59), 1150, .97),
        'Beacon': beacon_material(),
        'SealHalo': solid_material('M_NL1105_SealHalo',(.07,.62,.48),.28,.2,3.0),
    }
    mats['Landing'] = mats['Floor']
    return mats


def geometry_snapshot():
    """Existing geometry and serialized stage transforms; materials deliberately excluded."""
    rows = []
    stages = []
    for actor in ACTORS.get_all_level_actors():
        if actor.actor_has_tag(TAG): continue
        for c in actor.get_components_by_class(unreal.StaticMeshComponent):
            mesh = c.get_editor_property('static_mesh')
            row = {'actor': actor.get_name(), 'component': c.get_name(),
                   'mesh': mesh.get_path_name() if mesh else None, 'transform': transform_value(c.get_world_transform()),
                   'collision': str(c.get_collision_enabled()), 'navigation': bool(c.get_editor_property('can_ever_affect_navigation'))}
            if isinstance(c, unreal.InstancedStaticMeshComponent):
                row['instances'] = [transform_value(c.get_instance_transform(i, world_space=True))
                                    for i in range(c.get_instance_count())]
            rows.append(row)
        if isinstance(actor, unreal.NLLevelEncounterDirector):
            for s in actor.stages:
                stages.append({'id': str(s.stage_id), 'entry': transform_value(s.entry_transform),
                    'trigger': xyz(s.trigger_center), 'extent': xyz(s.trigger_extent),
                    'points': [{'id': str(p.spawn_point_id), 'transform': transform_value(p.spawn_transform)} for p in s.spawn_points],
                    'waves': [w.get_path_name() for w in s.waves], 'seed': s.seed})
    return {'geometry': sorted(rows, key=lambda r: (r['actor'], r['component'])), 'stages': stages}


def apply_materials(mats):
    for actor in ACTORS.get_all_level_actors():
        label = actor.get_actor_label()
        if not label.startswith(('NB_', 'NB2_', 'NB3_', 'NB4_')) or actor.actor_has_tag(TAG): continue
        for c in actor.get_components_by_class(unreal.StaticMeshComponent):
            for index in range(c.get_num_materials()):
                old = c.get_material(index)
                if not old: continue
                key = old.get_name().removeprefix('M_')
                if key == 'CloudMass': key = 'Cloud'
                if 'CloudBank' in label or 'CloudSea' in label: key = 'Cloud'
                # Repeated execution finds our own materials from the previous pass.
                if old.get_name().startswith('M_NL1105_'):
                    reverse = {'StoneFloor':'Floor','CarvedStone':'Stone','MountainRock':'Cliff',
                        'PaleRock':'CliffLight','JadeRoof':'Roof','Redwood':'Wood','AgedGold':'Trim',
                        'JadeSeal':'Accent','LanternAmber':'Warm','StoneJoint':'Joint','Pine':'Pine',
                        'IndigoCloth':'Banner','CloudSea':'Cloud'}
                    key = reverse.get(old.get_name().removeprefix('M_NL1105_'), key)
                if key not in mats: continue
                c.set_material(index, mats[key])
                REPORT['material_overrides'].append({'actor': label, 'component': c.get_name(), 'slot': index,
                    'before': old.get_path_name(), 'after': mats[key].get_path_name()})
    assert len(REPORT['material_overrides']) > 80, 'Expected substantial main-map-only material coverage'


class DecorationBuilder:
    def __init__(self, mats):
        self.groups = {}
        self.mats = mats
        self.audit = {r['path'].split('.')[0]: r for r in json.loads((O/'ArtAssetAudit.json').read_text(encoding='utf-8'))['mesh_assets']}

    def place(self, group, name, foot_m, height_cm, yaw=0, sink=0, far=False, floor=False, raise_cm=0, xy_ratio=1.0):
        path = '/Game/AsianTemple/Environment/Mesh/' + name
        assert path in self.audit, path
        mesh = A.load_asset(path); bounds = mesh.get_bounds()
        dimensions = [2*x for x in xyz(bounds.box_extent)]
        expected = self.audit[path]['dimensions_cm']
        assert max(abs(a-b) for a,b in zip(dimensions, expected)) < .1, (path, dimensions, expected)
        ratio = height_cm / dimensions[2]
        assert .05 <= ratio <= 6.0, (path, ratio, height_cm, dimensions)
        assert .5<=xy_ratio<=1.0, xy_ratio
        assert max(dimensions[:2]) * ratio * xy_ratio <= height_cm*2.5, (path, dimensions, height_cm)
        p = [x*100 for x in foot_m]
        if floor:
            result = unreal.SystemLibrary.line_trace_single(EDITOR.get_editor_world(), unreal.Vector(p[0],p[1],p[2]+150),
                unreal.Vector(p[0],p[1],p[2]-250), unreal.TraceTypeQuery.ECC_VISIBILITY, False, [], unreal.DrawDebugTrace.NONE)
            assert result, ('Decoration has no supported placement', group, p)
            hit = result.to_tuple(); impact = hit[5]
            assert abs(impact.z-p[2]) <= 120, ('Decoration ground differs from intended court', group, p, xyz(impact))
            p[2] = impact.z
        p[2]+=raise_cm
        center = xyz(bounds.origin); bottom = center[2]-bounds.box_extent.z
        angle = math.radians(yaw); co, si = math.cos(angle), math.sin(angle)
        # The authored foot target denotes the horizontal bounds center, not the arbitrary mesh pivot.
        local_x, local_y = center[0]*ratio*xy_ratio, center[1]*ratio*xy_ratio
        location = [p[0]-(local_x*co-local_y*si), p[1]-(local_x*si+local_y*co), p[2]-bottom*ratio-sink]
        key = (name, far)
        if key not in self.groups:
            actor = ACTORS.spawn_actor_from_class(unreal.NLBlockoutMeshCluster, unreal.Vector())
            actor.set_actor_label('NL1105_Art_' + name + ('_Far' if far else ''))
            actor.set_folder_path(FOLDER+'/Instances')
            actor.set_editor_property('tags', [unreal.Name(TAG)])
            c = actor.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            c.set_mobility(unreal.ComponentMobility.STATIC)
            c.set_static_mesh(mesh); c.set_collision_profile_name('NoCollision')
            c.set_editor_property('can_ever_affect_navigation', False)
            c.set_editor_property('generate_overlap_events',False)
            c.set_cast_shadow(not far)
            if far:
                for i in range(c.get_num_materials()): c.set_material(i, self.mats['Far'])
            self.groups[key] = (actor, c)
        actor, component = self.groups[key]
        transform = unreal.Transform(location=unreal.Vector(*location), rotation=unreal.Rotator(yaw=yaw), scale=unreal.Vector(ratio*xy_ratio,ratio*xy_ratio,ratio))
        index = component.add_instance(transform, world_space=True)
        extent = xyz(bounds.box_extent)
        points=[]
        for sx in (-1,1):
            for sy in (-1,1):
                for sz in (-1,1):
                    points.append(xyz(unreal.MathLibrary.transform_location(transform, unreal.Vector(center[0]+sx*extent[0],center[1]+sy*extent[1],center[2]+sz*extent[2]))))
        REPORT['decorations'].append({'group':group,'actor':actor.get_actor_label(),'instance':index,'mesh':mesh.get_path_name(),
            'foot_cm':p,'height_cm':height_cm,'scale':[ratio*xy_ratio,ratio*xy_ratio,ratio],'yaw':yaw,'collision':'NoCollision','affects_navigation':False,
            'bounds_min':[min(q[k] for q in points) for k in range(3)],'bounds_max':[max(q[k] for q in points) for k in range(3)]})

    def place_fixed(self,group,mesh,position_cm,scale,material,yaw=0):
        assert mesh and all(.01<=float(s)<=10 for s in scale), (group,scale)
        key=(mesh.get_path_name(),material.get_path_name())
        if key not in self.groups:
            a=ACTORS.spawn_actor_from_class(unreal.NLBlockoutMeshCluster,unreal.Vector())
            a.set_actor_label('NL1105_Art_'+mesh.get_name());a.set_folder_path(FOLDER+'/Instances')
            a.set_editor_property('tags',[unreal.Name(TAG)])
            c=a.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            c.set_mobility(unreal.ComponentMobility.STATIC)
            c.set_collision_profile_name('NoCollision');c.set_editor_property('can_ever_affect_navigation',False)
            c.set_editor_property('generate_overlap_events',False);c.set_static_mesh(mesh);c.set_material(0,material)
            self.groups[key]=(a,c)
        actor,c=self.groups[key]
        tr=unreal.Transform(location=unreal.Vector(*position_cm),rotation=unreal.Rotator(yaw=yaw),scale=unreal.Vector(*scale))
        index=c.add_instance(tr,world_space=True)
        bounds=mesh.get_bounds();origin=xyz(bounds.origin);extent=xyz(bounds.box_extent);points=[]
        for sx in (-1,1):
            for sy in (-1,1):
                for sz in (-1,1):
                    points.append(xyz(unreal.MathLibrary.transform_location(tr,unreal.Vector(origin[0]+sx*extent[0],origin[1]+sy*extent[1],origin[2]+sz*extent[2]))))
        REPORT['decorations'].append({'group':group,'actor':actor.get_actor_label(),'instance':index,'mesh':mesh.get_path_name(),
            'foot_cm':position_cm,'scale':scale,'yaw':yaw,'collision':'NoCollision','affects_navigation':False,
            'bounds_min':[min(q[k] for q in points) for k in range(3)],'bounds_max':[max(q[k] for q in points) for k in range(3)]})


def mesh_helper():
    source=P/'Scripts/Editor/NilinBlockout/ue_mesh_v02.py'
    spec=importlib.util.spec_from_file_location('nl1105_art_mesh_helper',source)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    return helper


def lantern_stand_mesh():
    # Closed, merged stone base, upright and cantilever. Its pivot is directly
    # below the lantern, so all ten assemblies have a clear attachment point.
    boxes=[((-.42,0,.1),(.7,.7,.2)),((-.42,0,1.38),(.18,.18,2.36)),
           ((-.1,0,2.64),(.9,.18,.18)),((0,0,2.57),(.1,.1,.14))]
    vv=[];tt=[]
    for p,size in boxes:
        offset=len(vv)
        for sx,sy,sz in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)):
            vv.append((p[0]+sx*size[0]/2,p[1]+sy*size[1]/2,p[2]+sz*size[2]/2))
        for tri in ((0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),
                    (1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)):
            tt.append(tuple(offset+i for i in tri))
    path=DEST+'/Meshes/SM_NL1105_LanternStand'
    if A.does_asset_exist(path):backup_file(material_file(path))
    return mesh_helper().make_asset(path,vv,tt,False)


def build_decorations(mats):
    b=DecorationBuilder(mats)
    stand=lantern_stand_mesh();cube=A.load_asset('/Engine/BasicShapes/Cube')
    def lamp(group,p,side):
        b.place(group+' suspended lantern','SM_Lamp_01a',p,90,floor=True,raise_cm=165)
        foot=list(REPORT['decorations'][-1]['foot_cm']);foot[2]-=165
        b.place_fixed(group+' stone standard',stand,foot,[1,1,1],mats['Stone'],yaw=0 if side<0 else 180)
    for side in (-1,1):
        b.place('Gate guardians','SM_Dragon_Statue_01a',(side*17,-18,0),300,yaw=0,floor=True,raise_cm=50)
        ground=list(REPORT['decorations'][-1]['foot_cm']);ground[2]-=25
        b.place_fixed('Guardian stone plinths',cube,ground,[1.6,5.7,.5],mats['Stone'])
        for y in (-4,14):lamp('Gate lamps',(side*21,y,0),side)
        lamp('Court entry lamps',(side*12,127,28),side)
        lamp('Court rear lamps',(side*24,150,28),side)
        lamp('Alchemy lamps',(side*25,284,72),side)
    for p,yaw in (((-26,17,0),25),((27,145,28),-34)):
        b.place('Foreground pines','SM_Tree_Big_01a',p,1000,yaw=yaw,floor=True)
    for p,yaw in (((26,18,0),-30),((-28,145,28),57),((28,290,72),-18),((-28,320,72),110)):
        b.place('Middle pines','SM_Tree_Medium_01a',p,720,yaw=yaw,floor=True)
    # Low detail belongs to the outer edge of the established shelves, behind
    # the unchanged cover. Caster capsules and route-to-hand firing paths stay clear.
    stations=[(-1,45.275,6.4),(1,177.075,34.4),(-1,233.703571428571,56.8)]
    for si,(side,y,z) in enumerate(stations):
        for i,name in enumerate(('SM_Rock_01a','SM_Rock_01b','SM_Rock_02a','SM_Rock_01a','SM_Rock_01b','SM_Rock_02a')):
            x=side*(15.7 + (.85 if i%2 else 0))
            yy=y-1.8+(i//2)*2.2
            height=(155,120,140,165,135,150)[i]
            b.place('R%02d outer rock skin'%(si+1),name,(x,yy,z+.25),height,yaw=31*i+43*si,sink=height*.23)
    far=[('SM_Cliff_01a',(190,160,-125),22000,18),('SM_Cliff_01a',(210,350,-125),22000,91),
         ('SM_Cliff_01c',(-250,180,-135),20000,12),('SM_Cliff_01c',(-360,400,-135),20000,65),
         ('SM_Cliff_01c',(230,470,-125),24000,-30),('SM_Cliff_01c',(-360,620,-125),24000,72)]
    for name,p,h,yaw in far: b.place('Distant mountain layers',name,p,h,yaw=yaw,far=True,xy_ratio=.65)
    assert len(REPORT['decorations'])==54, len(REPORT['decorations'])
    assert len(b.groups)<=12, len(b.groups)
    REPORT['instance_groups']=len(b.groups)


def segment_box(a,b,lo,hi):
    near,far=0.0,1.0
    for k in range(3):
        delta=b[k]-a[k]
        if abs(delta)<1e-8:
            if a[k]<lo[k] or a[k]>hi[k]:return False
        else:
            t0,t1=(lo[k]-a[k])/delta,(hi[k]-a[k])/delta
            near=max(near,min(t0,t1));far=min(far,max(t0,t1))
            if near>far:return False
    return far>1e-5 and near<1-1e-5


def validate_new_visual_clearance():
    layout=json.loads((P/'Docs/Gameplay/SpawnReview1104/SpawnLayout.json').read_text(encoding='utf-8-sig'))
    blocked=[]
    # Horizontal spawn clearance protects visible enemy entry and glyphs.
    for stage in layout['stages']:
        for point in stage['points']:
            p=point['position']
            for d in REPORT['decorations']:
                if 'Distant' in d['group']:continue
                lo,hi=d['bounds_min'],d['bounds_max']
                if lo[0]-100<p[0]<hi[0]+100 and lo[1]-100<p[1]<hi[1]+100 and lo[2]-100<p[2]<hi[2]+150:
                    blocked.append({'spawn':point['id'],'decor':d['group'],'mesh':d['mesh']})
    assert not blocked, blocked
    # Keep all newly added bounds clear of the central route-to-seal landmark ray.
    seal=[-20800,64900,15500]
    origins=[[0,-2100,170],[0,12600,2970],[0,27900,7370],[-13000,46600,10770]]
    rays=[]
    for origin in origins:
        hits=[d['group'] for d in REPORT['decorations'] if segment_box(origin,seal,d['bounds_min'],d['bounds_max'])]
        rays.append({'eye':origin,'seal_target':seal,'new_bounds_blockers':hits})
    assert not any(r['new_bounds_blockers'] for r in rays), rays
    REPORT['new_visual_clearance']={'spawn_capsules_clear':True,'seal_approach_rays':rays}


def tune_atmosphere():
    world=EDITOR.get_editor_world()
    fogs=[a for a in ACTORS.get_all_level_actors() if isinstance(a,unreal.ExponentialHeightFog)]
    if not fogs:
        fog=ACTORS.spawn_actor_from_class(unreal.ExponentialHeightFog,unreal.Vector(0,0,-2500))
        fog.set_actor_label('NL1105_Art_LayeredCloudSea');fog.set_folder_path(FOLDER+'/Atmosphere')
        fog.set_editor_property('tags',[unreal.Name(TAG)])
    else:
        assert len(fogs)==1, 'Inspect existing fog stack before tuning'
        fog=fogs[0]
    c=fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    c.set_editor_property('fog_density',.007)
    c.set_editor_property('fog_height_falloff',.075)
    c.set_editor_property('fog_inscattering_luminance',unreal.LinearColor(.52,.67,.69,1))
    c.set_editor_property('fog_max_opacity',.74)
    c.set_editor_property('start_distance',1800.0)
    c.set_editor_property('enable_volumetric_fog',False)
    second=c.get_editor_property('second_fog_data')
    second.set_editor_property('fog_density',.0008)
    second.set_editor_property('fog_height_falloff',.025)
    second.set_editor_property('fog_height_offset',6500.0)
    c.set_editor_property('second_fog_data',second)
    REPORT['atmosphere']={'fog_actor':fog.get_actor_label(),'base_density':.007,'second_density':.0008,
                          'start_distance_cm':1800,'volumetric_fog':False,'new_dynamic_lights':0}
    # Add warm natural highlights without increasing the number of shadow lights.
    for actor in ACTORS.get_all_level_actors():
        if isinstance(actor,unreal.DirectionalLight) and actor.get_actor_label().startswith('NB_'):
            component=actor.get_component_by_class(unreal.DirectionalLightComponent)
            component.set_light_color(unreal.LinearColor(1.0,.88,.73,1))


def strengthen_seal_landmark(mats):
    """A fixed emissive guide over the existing seal, with no light or gameplay component."""
    source=P/'Scripts/Editor/NilinBlockout/ue_mesh_v02.py'
    spec=importlib.util.spec_from_file_location('nl1105_art_mesh_helper',source)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    verts=[];triangles=[];segments=48;sides=8;radius=6.0;tube=.18
    for i in range(segments):
        theta=2*math.pi*i/segments
        for j in range(sides):
            phi=2*math.pi*j/sides;r=radius+tube*math.cos(phi)
            verts.append((r*math.cos(theta),r*math.sin(theta),tube*math.sin(phi)))
    for i in range(segments):
        for j in range(sides):
            a=i*sides+j;b=((i+1)%segments)*sides+j
            c=i*sides+(j+1)%sides;d=((i+1)%segments)*sides+(j+1)%sides
            triangles.extend(((a,b,d),(a,d,c)))
    path=DEST+'/Meshes/SM_NL1105_SealHalo'
    if A.does_asset_exist(path):backup_file(material_file(path))
    ring=helper.make_asset(path,verts,triangles,False)
    cylinder=A.load_asset('/Engine/BasicShapes/Cylinder')
    assert ring and cylinder
    definitions=[('SealGuideHalo',ring,[-20800,65800,17000],unreal.Vector(1,1,1),unreal.Rotator(pitch=90),mats['SealHalo']),
                 ('SealGuideBeam',cylinder,[-20800,65800,18200],unreal.Vector(1.6,1.6,24),unreal.Rotator(),mats['Beacon'])]
    for name,mesh,p,scale,rotation,material in definitions:
        a=ACTORS.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*p),rotation)
        a.set_actor_label('NL1105_Art_'+name);a.set_folder_path(FOLDER+'/Landmark')
        a.set_editor_property('tags',[unreal.Name(TAG)])
        c=a.get_component_by_class(unreal.StaticMeshComponent)
        c.set_mobility(unreal.ComponentMobility.STATIC);c.set_static_mesh(mesh)
        c.set_material(0,material);c.set_world_scale3d(scale)
        c.set_collision_profile_name('NoCollision');c.set_editor_property('generate_overlap_events',False)
        c.set_editor_property('can_ever_affect_navigation',False);c.set_cast_shadow(False)
    REPORT['seal_landmark']={'center_cm':[-20800,65800,17000],'halo_diameter_cm':1236,
        'halo_triangles':len(triangles),'beam_height_cm':2400,'beam_top_z_cm':19400,
        'cosmetic_actors':2,'collision':'NoCollision','dynamic_lights':0,'actor_tick':False}


CAMERAS=[
    ('Gate',(2700,-3050,1050),(0,-150,650),65),
    ('MartialCourt',(4100,10500,5400),(0,14500,3100),64),
    ('RangedRock',(700,3820,1620),(-820,4750,970),66),
    ('Alchemy',(3800,26900,9900),(0,30600,7900),65),
    ('Summit',(-17500,57500,15100),(-20800,64000,14500),65),
    ('Overview',(-33000,-38000,34000),(-9000,28500,6800),65),
]


def evidence_cameras():
    for name,p,target,fov in CAMERAS:
        a=ACTORS.spawn_actor_from_class(unreal.CameraActor,unreal.Vector(*p),
            unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*p),unreal.Vector(*target)))
        a.set_actor_label('NL1105_Art_CAM_'+name);a.set_folder_path(FOLDER+'/EvidenceCameras')
        a.set_editor_property('tags',[unreal.Name(TAG)])
        c=a.get_component_by_class(unreal.CameraComponent)
        c.set_editor_property('field_of_view',fov);c.set_editor_property('constrain_aspect_ratio',False)


def main():
    assert EDITOR.get_game_world() is None, 'End PIE before environment authoring'
    assert LEVEL.load_level(MAP)
    assert (O/'ArtAssetAudit.json').is_file() and (O/'SceneBaseline.json').is_file()
    map_path=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
    backup_file(map_path)
    REPORT['map_sha256_before']=hashlib.sha256(map_path.read_bytes()).hexdigest()
    # Only this task's removable cosmetic actors are retired during iteration.
    for actor in list(ACTORS.get_all_level_actors()):
        if actor.actor_has_tag(TAG):
            assert actor.get_actor_label().startswith('NL1105_Art_')
            assert ACTORS.destroy_actor(actor)
    before=geometry_snapshot()
    mats=build_materials()
    apply_materials(mats)
    build_decorations(mats)
    validate_new_visual_clearance()
    tune_atmosphere()
    strengthen_seal_landmark(mats)
    evidence_cameras()
    after=geometry_snapshot()
    assert before==after, 'A source collision, navigation, geometry or stage transform changed'
    assert len(before['stages'])==16, len(before['stages'])
    assert LEVEL.save_current_level(), 'Main map save failed'
    REPORT.update({'state':'passed','saved_utc':time.time(),'map_sha256_after':hashlib.sha256(map_path.read_bytes()).hexdigest(),
                   'existing_geometry_and_navigation_unchanged':True,'stage_count':len(before['stages']),
                   'gameplay_and_geometry_digest':digest(before),'source_material_packages_modified':False,
                   'scope':'Main-map material and cosmetic art authoring. Visual screenshots and runtime checks are separate.'})


O.mkdir(parents=True,exist_ok=True)
try:
    main()
except Exception:
    REPORT.update({'state':'failed','error':traceback.format_exc()})
    (O/'ArtApplied.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')
    raise
(O/'ArtApplied.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2),encoding='utf-8')
unreal.log('GDD_ORDERED_ART_SAVED '+REPORT['map_sha256_after'])
