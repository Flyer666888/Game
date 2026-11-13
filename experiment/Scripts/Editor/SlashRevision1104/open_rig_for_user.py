"""One-shot interactive entry; opens existing assets without modifying them."""
import json,time,traceback
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve()
O=P/'Docs/Gameplay/SlashRevision1104'
began=time.monotonic()
def open_assets(delta):
    if time.monotonic()-began<3:return
    unreal.unregister_slate_post_tick_callback(handle)
    try:
        cls=unreal.EditorAssetLibrary.load_blueprint_class('/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_sword')
        enemy=unreal.get_default_object(cls)
        assets=[enemy.enemy_skeletal_mesh,enemy.attack_animation,enemy.enemy_skeletal_mesh.skeleton]
        paths=[a.get_path_name() for a in assets]
        assert all(assets), 'The current native rig assets were not found.'
        editor=unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
        opened=[bool(editor.open_editor_for_assets([asset])) for asset in assets]
        unreal.EditorAssetLibrary.sync_browser_to_objects(paths)
        report={'state':'opened' if all(opened) else 'partial','assets':paths,'opened':opened,
                'note':'Interactive asset editors only; no animation baking, import, save, or worker runs.'}
    except Exception:
        report={'state':'error','error':traceback.format_exc()}
        unreal.log_error(report['error'])
    (O/'UserRigEditor.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
handle=unreal.register_slate_post_tick_callback(open_assets)
