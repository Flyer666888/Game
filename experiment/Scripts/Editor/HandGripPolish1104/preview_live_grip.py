"""Evaluate a hand candidate in real AI before changing Blueprint defaults."""
from pathlib import Path
import unreal,json
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/HandGripPolish1104'
C=json.loads((O/'FitCandidate.json').read_text(encoding='utf-8-sig'))
prepared=json.loads((O/('Prepared_'+C['id']+'.json')).read_text(encoding='utf-8-sig'))
source=P/'Scripts/Editor/PackDIntegration1104/validate_live_d.py'
code=source.read_text(encoding='utf-8-sig').replace('PackDIntegration1104','HandGripPolish1104')
code=code.replace("'A_Wuxia_Attack_PackD'",repr(prepared['clips']['attack']['asset']))
code=code.replace('d_live_probe=DLiveProbe()','')
code=code.replace("(O/'LiveD.json')","(O/'PreviewLiveD.json')")
exec(compile(code,str(source),'exec'),globals())
class PreviewProbe(DLiveProbe):
    def stage_tick(self):
        if self.enemy is None:
            g=C['grip'];grip=unreal.Transform(location=unreal.Vector(*g['p']),scale=unreal.Vector(*g['s']));grip.rotation=unreal.Quat(*g['q'])
            for enemy in self.owned(pause=False):
                for key,prop in {'attack':'attack_animation','idle':'idle_animation','walk':'walk_animation','hit':'hit_reaction_animation','death':'death_animation','cast':'cast_animation'}.items():
                    enemy.set_editor_property(prop,unreal.load_asset(prepared['clips'][key]['asset']))
                enemy.set_editor_property('sword_grip_transform',grip);enemy.sword.set_relative_transform(grip,False,True)
        super().stage_tick()
preview_probe=PreviewProbe()
