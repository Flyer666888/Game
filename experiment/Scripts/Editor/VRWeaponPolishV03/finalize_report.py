"""Collect the final V03 local-asset, UE-import and equipped-pose evidence."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parents[3]
OUT=P/'Docs/Gameplay/VRWeaponPolish_v03'
SRC=P/'ArtSource/WeaponReview/SelectedA_DetailV03'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
imp=read(OUT/'ImportReport.json');run=read(OUT/'RuntimeGripReport.json')
geo=read(SRC/'AssetReadbackReport.json');surface=read(SRC/'Textures/material_texture_contract.json')
assert imp['state']==run['state']==geo['state']==surface['state']=='passed'
assert len(run['poses'])==7 and not run['failures']
assert len(run['captures'])==5
assert run['map_unchanged'] and run['checkpoint_settings_restored']
assert read(OUT/'Status.json')['state']=='closed'
protected=[dict(path=x['Path'],before=x['Hash'].lower(),after=digest(Path(x['Path']))) for x in read(OUT/'ProtectedBaselineHashes.json')]
assert all(x['before']==x['after'] for x in protected)
fbx=SRC/'SM_PlayerSword_A_DetailV03.fbx'
mesh=P/'Content/ReversedScale/Weapons/SelectedSwordA_DetailV01/SM_PlayerSword_A_DetailV01.uasset'
assert digest(fbx)==imp['source_sha256']==geo['fbx_sha256']
assert digest(mesh)==run['mesh_sha256']
textures=[]
for name,spec in surface['files'].items():
    actual=digest(Path(spec['file']));assert actual==spec['sha256']
    textures.append({'name':name,'path':spec['file'],'sha256':actual})
excerpt=(OUT/'FinalImportExcerpt.log').read_text(encoding='utf-8-sig')
warnings=[line for line in excerpt.splitlines() if any(x in line for x in ('FBXImport: Warning','近零的切线','近零的副法线','Failed to compile Material','Traceback'))]
assert not warnings,warnings
result={'state':'passed','revision':'V03','direction':'Realistic Chinese dragon ornament and opaque ice jade, no emissive or translucent effects',
    'runtime_asset':run['equipped_mesh'],'runtime_asset_sha256':digest(mesh),'source_fbx_sha256':digest(fbx),
    'source_triangles':geo['triangles'],'ue_render_triangles':run['lod0_triangles'],
    'material_slots':7,'uv_channels':imp['uv_channels'],'textures':textures,
    'shader_authoring':imp['surface_authoring'],
    'final_import_warning_check':'No FBX, near-zero tangent/binormal, material compile failure or Python traceback in final import excerpt.',
    'saved_build_settings':imp['saved_build_settings'],'synthetic_grip_poses_passed':7,
    'screenshots':run['captures'],'protected_files':protected,'map_unchanged':True,'checkpoint_settings_restored':True,
    'physical_pico_acceptance':False,'performance_benchmark_run':False,'cpp_changed_or_rebuilt':False,
    'review_editor_closed':True,'launcher_preflight':read(OUT/'LauncherCheck.json'),
    'backup':'Backups/Content/ReversedScale/Weapons/SelectedSwordA_DetailV01',
    'preview_note':'Source Detail previews use Blender studio lights; Screenshots are actual UE VR-lab lighting with supplied grip poses.'}
(OUT/'FinalReport.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
notes=f'''主角剑 V03：写实龙纹与冰玉

已更新实际主角武器。护手与剑根增加龙纹装饰，剑首采用不透明冰玉，握柄改为深色皮革。
钢刃、旧银、皮革与冰玉采用独立的微表面粗糙度和法线贴图，保留清晰的剑脊、锋口和收尖轮廓。
纹理来自本地程序生成，没有下载新素材、付费生成或外部账号操作。

资产与运行时
源：ArtSource/WeaponReview/SelectedA_DetailV03，内含Blender、FBX、棚拍预览和Textures。
运行时沿用SelectedSwordA_DetailV01/SM_PlayerSword_A_DetailV01稳定路径，内容已更新为V03。
新材质/纹理位于该目录Materials/V03与Textures/V03；V02资料及旧材质保留。
FBX三角面：{geo['triangles']}；UE渲染三角面：{run['lod0_triangles']}；7材质槽，2UV通道，9张512像素贴图。
两种三角面数量分别来自源FBX读回与UE最终网格，不混用。

验证
独立FBX读回通过；最终UE导入、保存与包重新加载通过。
最终导入日志未发现近零切线/副法线或材质编译失败。
实际VR角色装备新资产，通过7种合成Grip方向检查；5张UE截图已保存。
9个保护文件SHA256未变，包含持剑代码、DLL、手模型、动作及关卡。未更改C++或重新编译。
PIE与隐藏验证编辑器已结束，临时检查点设置已恢复；入口只读检查通过。
本轮未进行真人PICO验收、完整战斗测试或性能基准测试。

预览与试玩
ArtSource中的Detail预览使用棚拍灯光；本目录Screenshots使用游戏原有场景灯光。
退出旧试玩后，双击工程根目录Run_VR_Demo.cmd进入现有VR测试关。

回滚
关闭UE后，将本目录Backups/Content/ReversedScale/Weapons/SelectedSwordA_DetailV01中的原文件覆盖回工程同名目录。
V03材质/纹理可保留，不影响旧网格；操作说明原件也在Backups中。
'''
(OUT/'修改与验证说明.txt').write_text(notes,encoding='utf-8')
print(json.dumps({'state':'passed','triangles':run['lod0_triangles'],'textures':len(textures),'protected_files':len(protected),'report':str(OUT/'FinalReport.json')},ensure_ascii=False))
