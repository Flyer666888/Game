import unreal,json
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve()
rows=[]
for key in ('talisman','rock_talisman','GM02','GM03'):
    path='/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_'+key
    obj=unreal.get_default_object(unreal.EditorAssetLibrary.load_blueprint_class(path))
    c=obj.get_component_by_class(unreal.NLTalismanAttackComponent)
    m=obj.get_component_by_class(unreal.SkeletalMeshComponent)
    rows.append({'asset':path,'role':str(obj.get_enemy_brain().role),'mesh':obj.enemy_skeletal_mesh.get_path_name(),
        'socket':str(c.muzzle_socket_name),'offset':str(c.muzzle_local_offset),'transform':str(c.talisman_hand_transform),
        'cast':obj.cast_animation.get_path_name() if obj.cast_animation else None,
        'timing':[obj.get_enemy_brain().telegraph_seconds,obj.get_enemy_brain().attack_seconds,obj.get_enemy_brain().recover_seconds]})
(P/'Docs/Gameplay/JadeTalismanCast1104/Baseline.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
