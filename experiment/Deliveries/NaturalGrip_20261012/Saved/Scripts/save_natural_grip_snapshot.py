"""Copy this batch's changed assets/source/evidence into a recoverable local snapshot."""
import hashlib
import json
import shutil
from pathlib import Path

project = Path(__file__).resolve().parents[2]
snapshot = project / 'Deliveries/NaturalGrip_20261012'
selected = [
    'experiment.uproject',
    'Run_SwordDuel_Demo.cmd', 'Run_SwordDuel_Demo.ps1',
    'Content/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Combat.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/M_WuxiaMale_Combat.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/M_WuxiaMale_Skin_Combat.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/BP_EnemySwordDisciple.uasset',
    'Content/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Death_Natural.uasset',
    'Source/experiment/Public/AI/NLEnemyCharacter.h',
    'Source/experiment/Private/AI/NLEnemyCharacter.cpp',
    'Source/experiment/Public/Animation/NLDeathBlendAnimInstance.h',
    'Source/experiment/Private/Animation/NLDeathBlendAnimInstance.cpp',
    'Binaries/Win64/UnrealEditor-experiment.dll',
    'Binaries/Win64/UnrealEditor.modules', 'Binaries/Win64/experimentEditor.target',
    'ArtSource/WuxiaMale/GripRefinement/WuxiaMaleCombat.blend',
    'ArtSource/WuxiaMale/GripRefinement/WuxiaMaleCombat.fbx',
    'ArtSource/WuxiaMale/NaturalDeath/NaturalDeathAuthoredPoses.json',
    'Docs/AI/State.md', 'Docs/AI/NaturalGripSaved-2026-10-12.json',
    'Docs/AI/NaturalGripDelivery-2026-10-12.json',
    'Docs/AI/SwordDisciplePrefabSaved.json',
    'Docs/AI/WaveNextTask-2026-10-12.json',
    'Docs/AI/BuildLog-NaturalGrip-2026-10-12.txt',
    'Docs/AI/NaturalGripImport-2026-10-12.log',
    'Saved/Scripts/import_enemy_combat_refinement.py',
    'Saved/Scripts/create_sword_disciple_prefab.py',
    'Saved/Scripts/capture_sword_duel_lab.py',
    'Saved/Scripts/bake_natural_death.py', 'Saved/Scripts/inspect_natural_death.py',
    'Saved/Scripts/save_natural_grip_snapshot.py',
    'Saved/Scripts/finalize_natural_grip_delivery.py',
]
selected += ['Content/ReversedScale/Maps/L_CombatLab' + suffix + '.umap'
             for suffix in ('SwordDuel', 'Reflection', 'Guard', 'Melee')]
rows = []
for relative in selected:
    source = project / relative
    if not source.is_file():
        continue
    destination = snapshot / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    rows.append({'relative_path': relative, 'bytes': source.stat().st_size,
                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})
manifest = {'date': '2026-10-12', 'scope': 'Recoverable snapshot of changed assets and source; uses unchanged project dependencies.',
            'files': rows, 'demo_entry': 'Run_SwordDuel_Demo.cmd in the main experiment project',
            'packaged_standalone': False, 'requires_local_ue58': True,
            'restore': 'With UE closed, restore selected files by their project-relative paths. Original assets and pre-change map backups remain in the project.'}
(snapshot / 'Manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('NATURAL_GRIP_SNAPSHOT_SAVED', len(rows), sum(r['bytes'] for r in rows))
