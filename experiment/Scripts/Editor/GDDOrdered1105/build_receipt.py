"""Record code/asset integrity for the authorized ordered GDD pass."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[3];O=P/'Docs/Gameplay/GDDOrdered1105'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
changes=[]
for before in (O/'Backups/Source').rglob('*'):
    if not before.is_file():continue
    relative=before.relative_to(O/'Backups');after=P/relative
    if after.is_file():
        a,b=sha(before),sha(after)
        if a!=b:changes.append({'path':relative.as_posix(),'before_sha256':a,'after_sha256':b})
new=[]
for name in ('NLWeakPointComponent.h','NLWeakPointComponent.cpp','NLStagingQueueTests.cpp','NLWeakPointTests.cpp',
             'NLOrdinaryLootSubsystem.h','NLOrdinaryLootSubsystem.cpp','NLOrdinarySupplyPickup.h','NLOrdinarySupplyPickup.cpp','NLOrdinaryLootTests.cpp'):
    files=list((P/'Source').rglob(name));assert len(files)==1,name
    f=files[0];new.append({'path':f.relative_to(P).as_posix(),'sha256':sha(f)})
protected=[]
previous=json.loads((P/'Docs/Gameplay/HandGripPolish1104/Delivery.json').read_text(encoding='utf-8-sig'))
for path,expected in previous['protected_sha256'].items():
    file=P/'Content'/(path.split('.')[0].removeprefix('/Game/')+'.uasset')
    protected.append({'asset':path,'matches':sha(file)==expected,'sha256':sha(file)})
jade=P/'ArtSource/Weapons/TalismanJade1104'
reference=json.loads((jade/'AssetValidation.json').read_text(encoding='utf-8-sig'))
for name,expected in reference['sha256'].items():
    file=jade/name;protected.append({'asset':str(file.relative_to(P)),'matches':sha(file)==expected,'sha256':sha(file)})
touched=[]
for file in (P/'Content').rglob('*'):
    if file.is_file() and file.suffix in ('.uasset','.umap') and file.stat().st_mtime>=1793885289:
        touched.append({'path':file.relative_to(P).as_posix(),'sha256':sha(file)})
report={'state':'passed' if all(x['matches'] for x in protected) else 'failed',
        'modified_existing_sources':changes,'new_sources':new,'protected_prior_rig_animation_sword_and_talisman':protected,
        'content_files_written_since_window_start':touched,
        'note':'Source comparison uses per-file initial backups. Content timestamps are an audit roster, not authorization to revert unrelated changes.'}
(O/'ChangeReceipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
assert report['state']=='passed'
print(json.dumps({'state':report['state'],'changed_source_count':len(changes),'new_source_count':len(new),'protected_count':len(protected),'content_written':len(touched)}))
