"""Apply the GDD's 30-HP / 30-damage ordinary melee baseline; no map edits."""
import hashlib, json, shutil
from pathlib import Path
import unreal

P = Path(unreal.Paths.project_dir()).resolve()
O = P / 'Docs/Gameplay/GDDSession28'
source = P / 'Content/ReversedScale/Combat/DA_YueyaoMelee.uasset'
backup = O / 'Backups/DA_YueyaoMelee.uasset'
if not backup.exists():
    shutil.copy2(source, backup)
asset = unreal.load_asset('/Game/ReversedScale/Combat/DA_YueyaoMelee')
assert asset
before = float(asset.get_editor_property('damage'))
assert before in (10.0, 30.0), f'Unexpected existing melee damage: {before}'
asset.set_editor_property('damage', 30.0)
assert unreal.EditorAssetLibrary.save_loaded_asset(asset, False)
assert float(asset.get_editor_property('damage')) == 30.0
level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
assert level.load_level('/Game/ReversedScale/Maps/L_NilinGameplayV01')
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
directors = [a for a in actors if isinstance(a, unreal.NLLevelEncounterDirector)]
assert len(directors) == 1
stages = []
for s in directors[0].get_editor_property('stages'):
    stages.append({'stage_id':str(s.stage_id), 'objective_id':str(s.objective_stable_id),
                   'waves':[w.get_path_name() for w in s.waves]})
report = {'success':True, 'before_damage':before, 'after_damage':30.0,
          'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
          'saved_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
          'main_map_modified':False, 'main_map_stages':stages,
          'scope':'Only the player melee definition changes. Blade Qi, enemy attacks, mesh, grip axes, and map are unchanged.'}
(O/'MeleeGDDAlignment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
