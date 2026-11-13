# 《逆鳞》资产就绪盘点

盘点日期：2026-10-02  
工程：UE 5.8.2 / `experiment`

## 已在工程中的可复用资产

| 内容 | 工程路径 | 盘点结果 | 对首个战斗切片的用途 |
|---|---|---|---|
| Asian Temple 环境 | `/Game/AsianTemple/` | 440 个文件：433 个 `.uasset`、7 个 `.umap`，约 2.58 GB | 已有日间关卡、地面、门、柱、墙与材质；先评估关卡里的平地/庭院，复用其环境构件 |
| 项目动作 | `/Game/Animations/` | 846 个 `.uasset` | 需要在 UE 资产浏览器确认序列骨架、动作含义、根运动和时长后再接敌人 |
| XR 框架 | `/Game/XRFramework/` | 67 个 `.uasset`、2 个 `.umap` | 可作为 Pawn、输入及 XR 交互参考；尚未完成 M1 验收 |
| 武器 | `/Game/Weapons/` | 27 个 `.uasset` | 可供之后主手武器表现/交互评估 |
| 用户武侠男角色 | `/Game/ReversedScale/Characters/WuxiaMale/` | 已制作基础绑定、重定向剑士待机；当前脸部保护版 65,000 三角面、身体 2K / 皮肤原始 4K 贴图 | `L_CombatLabWuxiaFeet` 的两名 Enemy 外观；正式跑动/攻击仍需逐段检查蒙皮 |

工程内的 Asian Temple 主要关卡文件：

- `/Game/AsianTemple/Map/LV_Temple_Day_ue5`
- `/Game/AsianTemple/Map/LV_Temple_Day`
- `/Game/AsianTemple/Map/Overview/LV_Overview`
- `/Game/AsianTemple/Map/Sublevel/` 下另有 4 个子关卡。

工程内可见的庭院构件包括 `BP_Floor_01a/b`、`BP_Temple_01a/b`、`BP_Temple_Door_01a`、`BP_Temple_Pillar_01a`、`BP_Temple_Wall_01a`，以及对应 Static Mesh。当前桌面运行画面仍显示黑暗水岩场景；因此“工程含有山门资产”不等于“当前战斗地图已正确使用山门庭院”。

## 收件箱中的待导入资产

| 收件箱 | 内容 | 处理决定 |
|---|---|---|
| `AssetInbox/3583AnimationsPack/` | 3,601 个 `.uasset` 和 1 个 `.umap`；工程同名内容目录目前只有 17 个文件 | 视为尚未完整导入。先检查骨架兼容与动作清单，再只导入第一场战斗所需动画，避免一次导入整包 |
| `AssetInbox/Asian Temple Pack/` | 两个旧版 `.zip`（4.26–4.27 与 5.0） | 工程已有 AsianTemple 内容；暂不重复导入旧版包 |
| `AssetInbox/C743 Fighting Stage Environment/` | `.rar` 场景包 | 暂不用于第一个切片；首个切片优先复用现有 AsianTemple 庭院 |
| `AssetInbox/D109 ZenGarden 5.2-5.3/` | `.zip` 与随附文本 | 与山门题材及首个切片无直接依赖，暂不导入 |
| `AssetInbox/Modular Asian Medieval City/` | `.zip` / `.rar` 城市场景包 | 暂不导入；先用已在工程内的 AsianTemple 完成战斗空间 |
| `AssetInbox/ue古风内饰/` | `.rar` 室内包 | 暂不用于户外山门战斗切片 |

本盘点只读资产文件/压缩包清单；没有解压、运行或导入收件箱中的归档文件。

## 下个资产步骤

1. UE 能够稳定编辑后，读取 `LV_Temple_Day_ue5` 的 Actor 名称、世界坐标和庭院范围；定位实际平地，决定复用关卡还是以其庭院构件搭建独立 Combat Lab。
2. 将战斗切片控制为一块平坦干燥区域、一个玩家出生点、两名敌人；敌人脚底落地、仅绕 Z 轴面向玩家。
3. 在 UE 资产信息中核对完整动作包的 Skeleton。选择两名敌人共用的 Idle、移动、攻击和受击序列，再建立可运行的动画蓝图/状态机；不要把单帧 Pose 或不兼容骨架的序列当成可播放动作。
4. 敌人运行时规则与伤害结算继续按资料包放在 C++，蓝图负责模型/动画/特效表现；当前资产盘点不能替代编译和运行验收。

## 当前依赖与风险

- 编译器阻塞已于 2026-10-08 解除：MSVC 14.44.35229 已安装，Runtime 模块的 Editor target 编译与类加载通过。
- UE MCP 未连接；需通过编辑器内可验证的 Python/MCP 工作流完成关卡读取和资产写入。
- 当前没有头显/OpenXR Runtime，无法验收 VR 追踪、双手操作或舒适度。

## 剑士动画补充盘点（2026-10-08）

- 已有 `/Game/Animations/Sword/`：164 个资产。已在 UE 读取 Anim_CSST、Anim_CS_IDL_01/02/03、Anim_CS_W_FWD、Anim_CSATLI_01/02，均为可读取的 AnimSequence，并与当前 Enemy mesh 的 UE4_Mannequin_Skeleton 一致。
- Demo 使用最稳定的基础待机 Anim_CSST；不用 IDL_03 等带较大身体摆动的插入动作。该待机没有 root 位移，首尾头部/脚部衔接接近，适用于原地循环预览。
- 剑术移动与轻攻击的候选片段含明显 root 平移；之后接 AI/攻击时应明确 root motion 与角色位移规则，不能直接作为原地循环动画播放。
- 选择记录见 SwordAnimationCandidates-2026-10-08.json；已替换两个 Enemy 并保存剑士版 demo，具体结果见 SwordAnimationReplacement-2026-10-08.json。


## Enemy 足底修复资产（2026-10-09）

- 当前模型 SK_WuxiaMale_Feet 保留脸部保护版的 65,000 三角面、皮肤 4K 与身体 2K 材质、原 UV 和共享骨架，仅修改下身蒙皮。源文件位于 ArtSource/WuxiaMale/FootCorrection/。
- 当前站立动画 Wuxia_Idle_Planted 已保存平地脚位与膝盖 IK 修正，长度 9.8667s；上下身待机仍持续播放。
- IK_WuxiaMale_Feet 与 RTG_Mannequin_WuxiaMale_Feet 提供两个脚部目标、Limb IK 及 Floor Constraint，供后续重定向继续使用。移动/攻击不能直接套用本次固定脚位烘焙。


## 玩家月曜武器（2026-10-09）

- 用户 Highlight.blend 已转为 SM_Yueyao_Player，九个材质槽、原始 2K 刀面与龙纹参考贴图、中心握柄枢轴均已接入。可编辑源副本与 FBX 位于 ArtSource/Weapons/Yueyao。
- 项目现有 SKM_MannyXR_right 可用；A_Yueyao_Grip_Right 合并 Grasp 和 IndexCurl 以闭合四指。右手、武器与袖口随第一人称相机显示。
- 当前是桌面运行效果。未来接入 XR 手柄时需将同一握柄挂点交给右手控制器，并单独安排动作、武器碰撞与 LOD。
