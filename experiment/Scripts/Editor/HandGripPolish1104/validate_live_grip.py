"""Reuse the real saved-map D regression probe against the fitted hand variants."""
from pathlib import Path
import unreal,json
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Docs/Gameplay/HandGripPolish1104'
C=json.loads((O/'FitCandidate.json').read_text(encoding='utf-8-sig'))
prepared=json.loads((O/('Prepared_'+C['id']+'.json')).read_text(encoding='utf-8-sig'))
sword=json.loads((O/'HiltImported.json').read_text(encoding='utf-8-sig'))['asset']
source=P/'Scripts/Editor/PackDIntegration1104/validate_live_d.py'
code=source.read_text(encoding='utf-8-sig').replace('PackDIntegration1104','HandGripPolish1104')
code=code.replace("'A_Wuxia_Attack_PackD'",repr(prepared['clips']['attack']['asset']))
code=code.replace('selected D. Real AI','selected D with the fitted hand. Real AI')
code=code.replace("row['root_curve']=", "row['sword_asset']=self.enemy.sword.static_mesh.get_path_name()\n        row['root_curve']=")
code=code.replace("self.report['checks'].update({", "self.report['checks'].update({'uses_fitted_enemy_sword':all(r['sword_asset']=="+repr(sword)+" for r in rows),")
exec(compile(code,str(source),'exec'),globals())
