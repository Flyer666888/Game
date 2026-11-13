"""Create a handoff only from successful final verification artifacts."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[3]
O=P/'Docs/Gameplay/GDDSession1101'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
tests=read(O/'Automation_02/index.json')
runtime=read(O/'RitualRuntimeFinal/RuntimeFirstLevel.json')
authored=read(O/'AuthoredValidation.json')
assert tests['failed']==0 and tests['notRun']==0
assert tests['succeeded']+tests['succeededWithWarnings']==85
assert runtime['success'] and all(runtime['checks'].values()) and not runtime['failures']
assert runtime['fixture_isolation']['state']=='restored_without_saving_map'
assert runtime['fixture_isolation']['temporary_assets_removed']
assert runtime['fixture_isolation']['full_stage_array_restored']
assert authored['success']
mapfile=P/'Content/ReversedScale/Maps/L_NilinGameplayV01.umap'
assert sha(mapfile)==authored['map_sha256']==runtime['fixture_isolation']['map_sha256_after']
binary=P/'Binaries/Win64/UnrealEditor-experiment.dll'
assert all(f.stat().st_mtime<=binary.stat().st_mtime for f in (P/'Source').rglob('*') if f.is_file())
baseline=P/'Docs/Gameplay/GDDSession28B/Backups/Source'
changes=[]
for f in sorted((P/'Source').rglob('*')):
    if not f.is_file():continue
    old=baseline/f.relative_to(P/'Source')
    if not old.exists() or sha(old)!=sha(f):
        changes.append({'path':f.relative_to(P).as_posix(),'sha256':sha(f),'baseline_exists':old.exists()})
report={'status':'complete','client_date':'2026-11-01','scope':'Level 02 ritual phase chain and FormationBreaker integration',
        'build_exit_code':int((O/'Build_02.exitcode').read_text(encoding='utf-8-sig').strip()),
        'automation':{k:tests[k] for k in ('succeeded','succeededWithWarnings','failed','notRun')},
        'runtime_checks':runtime['checks'],'phase_entries':runtime['phase_entries'],
        'breaker_observation':runtime['breaker_observation'],'retry_attempts':runtime['retry_attempts'],
        'final':{k:v for k,v in runtime['final'].items() if k!='growth'},
        'growth':{k:v for k,v in runtime['final']['growth'].items() if k!='event_ids'},
        'fixture_restored':True,'map_sha256':sha(mapfile),'module_sha256':sha(binary),
        'source_differences_since_phase_work_started':changes,
        'limits':['Scripted main-map integration; most enemies paused and cleared through ordinary-damage resolver contacts.',
                  'One breaker used live native navigation, scheduling, channel and projectile collision.',
                  'Not a human continuous playthrough, physical PICO test, or performance benchmark.'],
        'next_gdd_task':'BOSS-01: single flying sword, reflected guard damage, guard break, five-second vulnerability, recovery'}
assert report['build_exit_code']==0
(O/'VerificationSummary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
old=read(P/'Docs/Gameplay/GDDSession28B/Session.json')
old.update(status='completed_and_verified',verification='Docs/Gameplay/GDDSession1101/VerificationSummary.json',completed_client_date='2026-11-01')
(P/'Docs/Gameplay/GDDSession28B/Session.json').write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'success':True,'tests':85,'phase_count':len(runtime['phase_entries']),
                  'map_sha256':report['map_sha256'],'source_difference_count':len(changes)}))
