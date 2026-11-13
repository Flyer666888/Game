"""Summarize completed native-rig work from its actual verification reports."""
import json,hashlib
from pathlib import Path
P=Path(r'D:/game design/experiment');O=P/'Docs/Gameplay/SlashRevision1104'
def read(name):return json.loads((O/name).read_text(encoding='utf-8-sig'))
automation=read('Automation/index.json')
assert automation['failed']==0 and automation['notRun']==0
motion=read('MotionRuntime.json');capture=read('DemoCapture.json');blade=read('BladeUEVerification.json')
saved=read('SavedNativeVerification.json');video=read('NativeSlashDemo.json')
for report in (motion,capture,blade,saved):assert report['state']=='passed'
assert len(capture['frames'])==100
assert all(abs(f['animation_time']-f['actual_time'])<.001 and f['asset']!='None' for f in capture['frames'])
video_file=Path(video['output']);assert video_file.is_file()
result={'state':'passed','provided_native_bones':41,'enemy_archetypes':['sword','GM01','GM04','boss'],
 'source_fbx_unchanged':saved['source_fbx_unchanged'],'animation_seconds':1.65,
 'minimum_contact_blade_edge_dot':blade['minimum_contact_tip_edge_dot'],
 'animation_import_tip_error_cm':blade['maximum_centerline_tip_import_error_cm'],
 'runtime_checks':motion['checks'],'runtime_max_chase_speed_cm_s':max(r['speed'] for r in motion['frames']),
 'runtime_min_player_health':min(r['player_health'] for r in motion['frames']),
 'automation':{k:automation[k] for k in ('succeeded','succeededWithWarnings','failed','notRun')},
 'video':{'path':str(video_file),'seconds':video['duration_seconds'],'fps':video['fps'],
  'sha256':hashlib.sha256(video_file.read_bytes()).hexdigest()},
 'preview_scope':'Actual equipped Unreal mesh/materials, 60 Hz clip samples with AI and damage disabled for animation review.',
 'hardware_scope':'No physical HMD/controller playtest or headset performance measurement in this revision.'}
(O/'DeliveryVerification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
notes='''2026-11-04 新骨架劈砍 v07

已把用户提供的古代男青年走路动画 FBX 原生 41 骨架应用到 sword、GM01、GM04、boss 四类持刀敌人。
保留来源文件、原始蒙皮与旧 v06 资产，规范模型为 180 cm，校正原行走片相对绑定姿态的 90 度偏转。
新攻击为 1.65 秒：过肩蓄力、转髋带肩、跨身斜劈、完整随挥和收招。
按刀的实际几何验证锋刃（local -X）与切割方向一致；握刀改挂 RightHand，闭指包住刀柄。
待机、行走、受击、死亡与施法动画均使用同一新骨架；追逐速度保留 285–310 cm/s，按实测步幅同步播放。
同时修复命中死亡回调清空刀刃历史数组造成的崩溃，并补足同步取消/重启/销毁回归。
头部的厘米眼位偏移不再被 FBX 骨骼单位缩放放大，头显中立眼高校准同步到新守势。

验证结果见 DeliveryVerification.json。视频 NativeSlashDemo.mp4 为游戏内真实资源的逐帧动作预览：两次原速、一次半速；AI和伤害在录制时关闭。
完整主关卡 AI 追击和真实命中已另行验证。未进行实机头显性能或舒适度测试。
'''
(O/'更新说明.txt').write_text(notes,encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
