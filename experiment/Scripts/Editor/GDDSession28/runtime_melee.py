"""Reuse the existing isolated opening movement/sweep probe; stop after one kill."""
from pathlib import Path
import unreal
P = Path(unreal.Paths.project_dir()).resolve()
source = P / 'Scripts/Editor/Level01PolishV01/runtime_first_level.py'
code = source.read_text(encoding='utf-8-sig')
assert code.count('first_level_probe = FirstLevelProbe()') == 1
code = code.replace('first_level_probe = FirstLevelProbe()', '')
context = {'__name__':'gdd28_opening_probe', '__file__':str(source)}
exec(compile(code,str(source),'exec'), context)
context['O'] = P / 'Docs/Gameplay/GDDSession28/MeleeRuntime'

class GDD28OpeningProbe(context['FirstLevelProbe']):
    def physical_opening(self):
        super().physical_opening()
        if self.phase == 'death_retry':
            hits = self.report['physical_opening']['native_blade_results']
            assert len(hits) == 1, f'Expected one melee hit, got {len(hits)}'
            assert abs(hits[0]['damage'] - 30.0) < 0.01
            self.report['checks']['one_native_sweep_kills_ordinary_30_hp_enemy'] = True
            self.report['checks']['defeat_reward_awarded_once'] = True
            self.report['scope'] = [
                'Saved main map, actual CharacterMovement and StartDesktopSlash native sweep against one live sword AI.',
                'Other enemy paused. Scripted automation, not physical VR input or continuous playthrough.',
                '10-damage fixture checks 1.25 upgrade multiplier before isolated opening. No healing/invulnerability during opening.',
                'No map or user profile saved; unique test run and fixture assets cleaned by existing probe.'
            ]
            self.finish()

gdd28_opening = GDD28OpeningProbe()
