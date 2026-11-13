"""Read-only capture of the existing lab illumination; do not alter the level."""
import json
from pathlib import Path
import unreal
out = Path(unreal.Paths.project_dir())/'Docs/Gameplay/VRWeaponPolish_v02'
rows = []
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if not isinstance(actor, (unreal.SkyLight,unreal.DirectionalLight,unreal.PointLight,unreal.SpotLight,unreal.RectLight)):
        continue
    components = actor.get_components_by_class(unreal.LightComponentBase)
    for component in components:
        row={'actor':actor.get_actor_label(),'class':actor.get_class().get_name(),
             'rotation':str(actor.get_actor_rotation()),'properties':{}}
        for name in ['intensity','light_color','indirect_lighting_intensity','volumetric_scattering_intensity',
                     'mobility','visible','source_type','cubemap','lower_hemisphere_is_black','lower_hemisphere_color',
                     'real_time_capture','source_cubemap_angle','affects_world']:
            try:row['properties'][name]=str(component.get_editor_property(name))
            except Exception:pass
        rows.append(row)
report={'world':world.get_path_name(),'lights':rows,'console':{},'read_only':True}
for name in ['r.ForwardShading','r.ReflectionEnvironment','r.SkyLightingQuality','r.DefaultFeature.AutoExposure','r.ReflectionMethod','r.SSR.Quality','sg.ReflectionQuality']:
    report['console'][name]=unreal.SystemLibrary.get_console_variable_int_value(name)
(out/'LightingReadback.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
