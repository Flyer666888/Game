"""Initial held-art capture of the selected A; no player inputs or enemy start."""
from pathlib import Path
import unreal

root=Path(unreal.Paths.project_dir())
source=(root/'Saved/Scripts/capture_player_hand_presentation.py').read_text(encoding='utf-8')
for old,new in {
    'PlayerHands_Equipped.png':'SelectedSwordA_Equipped.png',
    'PlayerHands_BothGrip.png':'SelectedSwordA_BothGrip.png',
    'PlayerHandsInitialPresentation-2026-10-15.json':'SelectedSwordAPresentation-2026-10-16.json',
    "'date': '2026-10-15'":"'date': '2026-10-16'",
}.items():
    source=source.replace(old,new)
extra='''        weapon = player.get_editor_property('held_weapon')
        _hand_capture_report['held_weapon'] = weapon.get_editor_property('static_mesh').get_path_name()
        if 'SelectedSwordA/SM_PlayerSword_A' not in _hand_capture_report['held_weapon']:
            raise RuntimeError('The selected weapon A was not equipped')
        _hand_capture_report['weapon_materials'] = [weapon.get_material(i).get_path_name() for i in range(weapon.get_num_materials())]
        _hand_capture_report['weapon_relative_transform'] = str(weapon.get_relative_transform())
        blade = player.get_editor_property('blade')
        _hand_capture_report['blade_samples_cm'] = {name: str(blade.get_editor_property(name)) for name in ('blade_root_local','blade_mid_local','blade_tip_local')}
'''
source=source.replace("        _hand_capture_report['health'] =",extra+"        _hand_capture_report['health'] =")
exec(compile(source,__file__,'exec'),globals())
