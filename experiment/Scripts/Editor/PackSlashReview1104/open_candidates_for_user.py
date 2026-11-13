"""Open the four verified package candidates for interactive comparison; never save assets."""
import unreal,json,time,traceback
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve()
O=P/'Docs/Gameplay/PackSlashReview1104'
began=time.monotonic()
def open_candidates(delta):
    if time.monotonic()-began<3:return
    unreal.unregister_slate_post_tick_callback(handle)
    try:
        manifest=json.loads((O/'CandidateManifest.json').read_text(encoding='utf-8'))
        names=['Pack_Anim_CSAT_heavy_01','Pack_Anim_CSAT_heavy_02','Pack_Anim_CSATLI_03','Pack_Anim_CSATLI_04']
        paths=[next(c['asset'] for c in manifest['clips'] if c['name']==name) for name in names]
        assets=[unreal.load_asset(p) for p in paths]
        assert all(assets)
        editor=unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
        opened=[bool(editor.open_editor_for_assets([a])) for a in assets]
        unreal.EditorAssetLibrary.sync_browser_to_objects(paths)
        report={'state':'opened' if all(opened) else 'partial','assets':paths,'opened':opened,
                'note':'Interactive comparison only. No retarget job, worker, or asset saving.'}
    except Exception:
        report={'state':'error','error':traceback.format_exc()}
        unreal.log_error(report['error'])
    (O/'UserCandidateEditor.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
handle=unreal.register_slate_post_tick_callback(open_candidates)
