# 《逆鳞》开发状态

本文件记录 UE5.8 AI 开发资料包中的计划与当前工程证据。计划表不代表任务已完成。

## 最新交付（2026-10-12）

### 死亡动作优化

依据用户试玩反馈，死亡动作已更新为 `Wuxia_Death_Settle`：一次失衡侧倒，落地松弛，最后 0.5 秒保持静止，总长 3.2 秒。动作作者轨迹中的最大根高度单帧变化由 16.07cm 降至 1.24cm；头、颈和腿部摆动已收敛，原模型和权重保持原样。

原生播放增加 0.18 秒从当前姿态进入死亡的过渡；动画实例在安全 Tick 中切换，并立即求值首帧，避免切换时闪默认姿态。完整编译通过，SwordDuel/Reflection/Guard/Melee 四张地图已保存新引用并各自保留旧地图备份。初始场景确认当前两个 Enemy 都加载了新死亡动作；真实致命命中后的过渡等待用户试玩，未运行自动化测试。证据：`DeathRefinementDelivery-2026-10-12.json`。

当前入口已更新为 `Run_SwordDuel_Demo.cmd` / `Run_CombatLab_Demo.cmd`，打开独立持剑场景 `L_CombatLabSwordDuel`。两名弟子默认不攻击，按 G 开始交战；F 单独开启弹丸训练。玩家近战伤害仍为 10。

本批完成移动动画收敛、地面导航配置、原生动画通知伤害窗，以及带身份、攻击 GUID、方向和预计命中时间的攻击调度请求。源码完整编译退出码 0，动画/地图保存成功，初始持刀与脚部呈现已采集并查看。真正的追击、命中、格挡和暂停恢复等待用户试玩，没有添加或运行自动化测试。

当前状态与证据以 [State.md](State.md)、[试玩说明](SwordDuelQuickstart.md) 和 `SwordDuelDelivery-2026-10-12.json` 为准。精准反弹另保留 `Run_ReflectionLab_Demo.cmd`。此前五小时自动续接任务已设为 PAUSED；当前批次由用户恢复消息授权。

下文包含早期环境与历史原型记录；其中旧地图、旧 PID 和当时未实现项不代表最新交付状态。

## 环境基线（M0）

| 项目 | 当前记录 | 状态 |
|---|---|---|
| Unreal Engine | 5.8.2，`D:\浏览器下载\UE_5.8\Engine` | 已核实 |
| 工程 | `experiment.uproject`，当前目录名 `experiment` | 已核实 |
| 编译器 | Build Tools 2022 17.14.37710.0，MSVC 14.44.35229，`D:\UEBuildTools2022` | 已安装；游戏 Runtime 模块的 Editor Development 构建通过，退出码 0 |
| Windows SDK | 10.0.22621.0 | 已发现 |
| 目标设备 | Windows PC VR、双手柄为设计目标；具体头显与 OpenXR Runtime 尚未确定 | 待确认 |
| 当前机器 | RTX 4060 Laptop GPU；没有 VR 头显，需先用桌面模式观察 | 已核实 |
| C++ 工程基线 | 已恢复 `Source/` 并注册 `experiment` Runtime 模块；原归档保留 | UHT/C++ 编译、链接和六个原生类加载通过；玩法验收待进行 |
| Unreal MCP | 工程无连接配置；引擎有 Epic MCP Client Toolset，但未发现 Unreal MCP server；当前会话无 UE 专用 MCP tools | 未连接，详见 `Docs/AI/Capabilities.md` |

资料包全文及概念图已归档到 `Docs/AI/ReferencePack/`。AI-01 检查结果记录于 `Docs/AI/Capabilities.md`：当前会话没有 UE 专用工具，UE 安装中的 MCP Client Toolset 也不是可连接的编辑器 MCP 服务端；未配置 endpoint，故连接和读写探针仍为 NotRun。

## 当前原型

- 当前桌面测试关卡：`/Game/ReversedScale/Maps/L_CombatLabWuxiaFace`；此前 Wuxia/Sword/Lite 与原始场景保留。
- 轻量关卡含平整地面、山门和柱子、两个用户提供的武侠男角色、简单灯光与操作提示。模型新建了基础骨架和蒙皮，待机由 `Animations/Sword/Anim_CSST` 重定向到该骨架。
- 新建 `BP_DesktopPreviewPawn` 与 `BP_DesktopPreviewGameMode`，仅在轻量关卡覆盖 GameMode。键鼠观察使用引擎原生 DefaultPawn；工程的 XR 模板与默认 VR GameMode 保留用于后续 M1。
- AsianTemple 已导入；其余收件箱压缩包按需接入，资产盘点见 `AssetReadiness.md`。
- 这些敌人目前仍是关卡 Actor，不构成运行时敌人 AI；路径导航曾为规避模板地图的大规模 NavMesh 资源构建而关闭。
- 按方案第 11 节写的敌人状态机与攻击导演已从归档恢复到 `Source/experiment/`，完成编译和原生类加载。源码含主动人数上限、名额和命中错峰、生命周期释放、状态事件与导航失败改位；尚未替换关卡中的预览 Actor，也未验收运行时 AI 行为。
- 当前桌面启动入口：`Run_CombatLab_Demo.cmd` / `Run_CombatLab_Demo.ps1`，指定轻量地图并使用 `-nohmd -unattended`。

## 下一步

1. 游戏 Runtime 模块已恢复，`experimentEditor Win64 Development` 实际构建及 UE 原生类加载检查均通过。下一步按资料包顺序完成模块行为验收与场景接入。
2. Python 命令行读写已通过；Turnkey 启动等待由 `-unattended` 处理。继续完成轻量地图实际画面与键鼠体验复核。
3. 按资料包依赖顺序验收 M1 VR Pawn、输入、暂停和追踪状态；之后进入 CORE/COMBAT，再实现 ENEMY-01 和 DIR-01。

## 历史构建记录（2026-10-02，阻塞已于 2026-10-08 解除）

- 命令：UE 5.8 `Build.bat experimentEditor Win64 Development -Project=<experiment.uproject> -WaitMutex`。
- 结果：退出码 `6`，`Result: Failed (OtherCompilationError)`。
- 原因：UBT 明确禁止已安装的 MSVC `14.40.0–14.43.99999` 工具链；需要另一版本，日志推荐 `14.50.35717`。
- 最小 C++ 源码与 Target 文件已添加，但本轮未产生可运行的 Editor 二进制。
- VS Installer 仅发现 VS2022 Community `17.11.35312.102`；本机没有第二套符合要求的 Visual Studio/toolchain 可供切换。
- 项目当前没有 `Binaries/Win64`。为保持原蓝图工程可打开，本次从 `.uproject` 撤回未编译 Runtime 模块注册；C++ 草稿已归档保留，安装匹配工具链并成功构建后再移回模块目录并注册。
- UE 自动发现仍从旧 `Intermediate/TargetInfo.json` 触发 C++ build；已将根目录 `Source/` 和陈旧 `Intermediate/TargetInfo.json`、`Intermediate/Build/BuildRules` 可逆归档到 `Docs/AI/CodeDraft/`，未删除。
- 归档后蓝图桌面版通过运行入口并加载地图。重新启用 C++ 工程前需先安装兼容工具链，将草稿移回根目录 `Source/`，恢复模块注册并实际编译。
- 另以现有 `clang-cl 19.1.7`（UE 最低要求 18.1.8）配 MSVC14.41/VS2022 尝试过 `-Compiler=Clang -VCToolchain=VisualStudio2022`；UBT 仍因唯一 VS 工具链 14.41 位于禁用区间而退出 6。临时 Clang 设置和模块注册已撤回；未编译任何 C++ 源文件。
- UE 安装内 `Engine/Config/Windows/Windows_SDK.json` 显示 VS2026 工具集 `14.50.0–14.50.35722` 也在禁用列表，尽管 UBT 错误文本把 `14.50.35717` 写作推荐值；实际应选 `14.50.35723+`，或 VS2022 `14.44.35211+`（`14.44.0–14.44.35210` 同样被禁用）。

## 桌面预览验证（2026-10-02）

- 启动方式：`UnrealEditor.exe experiment.uproject -game -windowed -ResX=1600 -ResY=900 -DDC-ForceMemoryCache -nohmd`。
- 结果：进程 PID `35180` 存活；窗口标题为 `experiment (64-位 Development PCD3D_SM6)`。
- 日志证据：`Saved/Logs/experiment.log` 记录 `L_ShanmenCombat` 的 `LoadMap complete`、`Bringing World ... up for play`。
- 限制：本回合没有可用的原生桌面截图桥接，故窗口内的姿势、动画和画面质量尚未做视觉确认。VR 头显也未接入。

## 实际画面复核（2026-10-02）

- 通过已连接的原生窗口只读截图复核了 `-nohmd` 运行画面。
- 观察结果：四个 mannequin 当前直立，没有倒置；但它们分散站在水边岩坡和石块上，视野是黑暗岩洞/水面，没有山门庭院；也没有可见的攻击或移动，仍为静态关卡 Actor。
- 判定：只通过“UE 能加载关卡并进入 Play”，不通过“山门 Combat Lab 场景与敌人行为”。原型场景需要改为平坦、干燥、可导航区域，并先按资料包用两名近战敌人构成最小闭环。
- 头显和 OpenXR Runtime 未安装/接入；此截图只验证桌面图像，不代表 VR Pawn、双手输入或舒适度通过。

## 资产就绪盘点（2026-10-02）

- 盘点记录见 `Docs/AI/AssetReadiness.md`。
- AsianTemple 环境已在工程中，共 440 个文件（433 个资产、7 个地图），约 2.58 GB；包含日间地图与门、柱、墙、地面构件。当前屏幕画面仍非山门庭院，地图关卡内的庭院位置/Actor 坐标需要编辑器读取后确认。
- 收件箱的 `3583AnimationsPack` 有 3,601 个资产及 1 个地图；工程中的同名内容目录仅 17 个文件，动作包没有完整接入。先检查骨架，再择需导入 Idle、移动、攻击、受击动作。
- 项目 `/Game/Animations/` 另有 846 个资产，但其骨架与动画语义尚未逐项验证，不能据资产名认定可用于敌人。
- 其他收件箱场景压缩包本轮没有解压或导入；AsianTemple 已满足首个户外切片的环境基础。
- 首个可验收场景目标明确为一处平地、一个出生点、两名站姿正确且后续可驱动动画的敌人；运行时 AI 与伤害仍须走资料包要求的 C++ 路线。

## CORE-01 结算契约草稿（2026-10-02）

- 新增 C++ 草稿位于 `Docs/AI/CodeDraft/Source/experiment/Public/Combat/` 与 `Private/Combat/`：战斗接触/结果类型、攻击定义 Data Asset、每个运行时对象的战斗身份组件，以及 World Subsystem 统一结算入口。
- 结算器按 `AttackInstanceId + TargetRuntimeId + ProjectileGeneration` 去重，因此一次挥砍可命中多个目标，但同一次挥砍不能重复伤害同一目标；弹丸对象复用可用 generation 区分。身份组件提供 Player/Enemy/Objective/World 阵营，并在应用伤害前做基础阵营过滤。
- 结果携带 Result、Attack、Source、Target ID、结果类别、实际伤害和 FeedbackTag，并通过单一事件广播；防御/精准反弹/护势尚未实现，留给 CORE-02 与 COMBAT-03/04 接入该契约。
- 草稿尚未移入工程 `Source/`、未注册模块、未编译、未运行，也没有声明 CORE-01 验收通过。需先恢复受支持的 MSVC 工具链，然后根据 UHT/编译输出修订。
- 工具链复核：`vswhere` 当前仅发现 VS2022 17.11.4；磁盘上仅有 MSVC 14.41.34120，仍被 UE 5.8.2 禁用。安装目标按本机 `Windows_SDK.json` 中的允许区间选择：14.44.35211+ 或 14.50.35723+。


## 首轮 Combat Lab 站位修复（2026-10-02）

- 保留原地图 `L_ShanmenCombat`，从它复制出独立测试地图 `L_CombatLab`，不覆盖原始关卡。
- 修复玩家出生点：从世界坐标 `(0, 800, -5116)` 移至门前平地 `(-15000, 3900, -532)`；两个近战灰盒移至 `(-14700, 4200, -622)`、`(-14400, 4500, -622)`，俯仰和翻滚均为 0，仅绕 Z 轴面向玩家；移除额外攻击型/施法型两个静态灰盒。
- UE Python 编辑器脚本成功保存关卡；位置/旋转验收快照在 `Docs/AI/CombatLabBuild.json`。这只能证明关卡数据写入成功，尚未证明画面和角色动画通过试玩。
- `DefaultEngine.ini` 的 EditorStartupMap 与 GameDefaultMap 指向 `L_CombatLab`；桌面启动脚本为 `Run_CombatLab_Demo.ps1`。
- 本次运行预览尚未进入关卡：UE 启动阶段停在 Turnkey `VerifySdk`，日志没有 `LoadMap complete`。故仍需在用户侧 UE 编辑器打开 `L_CombatLab` 并点 Play 做画面确认。
- M1 控制器/移动、CORE-01 结算、敌人运行时 AI 均未完成或验收；C++ 实现仍被 MSVC 14.41 不兼容阻塞，现有敌人仍是静态关卡 Actor。这轮交付的是可检查的场景站位修正，不能当作战斗功能已完成。


## 轻量山门桌面测试（2026-10-08）

- 原完整环境副本此前在纹理压缩阶段申请约 1.7GB 内存时因页面文件不足崩溃；本次桌面测试改用 `L_CombatLabLite`，原地图保留。轻量地图只有 12 个 Actor，不包含 4,204 个原场景实例。
- UE Python 成功保存地图和两个预览蓝图，构建退出码 0。地面顶面 Z=0，范围包含山门、两根柱子和两名模型；地面使用简单材质，避免加载展示地面的额外大纹理。
- 预览专用 `BP_DesktopPreviewPawn` 使用引擎 DefaultPawn 的原生键鼠输入，保存的移动速度为 450cm/s。`BP_DesktopPreviewGameMode` 仅覆盖轻量地图。该观察模式不是 M1 VR Pawn 验收。
- 模型与 `Anim_L_Idle` 使用相同的 UE4 Mannequin 骨架，动作长约 3.1s。读取重新打开地图后的播放数据确认 looping/playing=true；抽样压缩动作的 0、0.75、1.5、2.25、3s 姿势，头部均在骨盆/脚部上方且位置随时间变化。审计退出码 0，报告见 `DesktopPreviewAudit.json`。
- 修复 SkeletalMeshActor 的根组件旋转覆盖：将 +Y 朝向偏移与对准玩家的 yaw 一次性写到 Actor，禁止另设根组件相对 yaw。重新读取后的两名模型朝向误差小于 0.00001 度，roll/pitch=0。
- 依据资料包原型基线，关闭 RayTracing、Lumen GI/reflections、虚拟阴影、Mesh Distance Fields，保留 Forward/MSAA。原配置在 `DefaultEngine-before-desktop-2026-10-08.ini`。
- 启动脚本使用 `-unattended` 绕过 Turnkey 的编辑器 SDK 启动等待，并指定可写 ShaderWorkingDir、`-DDC=(InstalledEnginePak,Local)` 及持久磁盘缓存。日志确认缓存 Writable；六个本地着色器进程用于首次编译。受限启动在日志初始化前退出，允许 UE 初始化用户目录后可正常工作。
- 启动入口：双击 `Run_CombatLab_Demo.cmd`。操作：WASD 移动、鼠标转视角、E/空格上升、Q/C/Ctrl 下降、Alt+F4 退出。观察模式可升降，不代表角色地面移动已实现。
- 本版供检查山门、出生视角、站位、待机姿势与镜头控制；没有伤害、追击、攻击或波次调度。C++ 草稿仍未编译；VS/MSVC 本次复核仍只有 14.41.34120，需要安装本机 UE 配置允许的 14.44.35211+ 或 14.50.35723+。
- 当前运行结果以 `Saved/Logs/DesktopPreview.log` 和下面补充的实际画面记录为准，不能把资产写入与姿势数据审计当作试玩通过。
### 运行与画面复核

- 修正版构建退出码 0。关闭预览释放资源文件后成功保存；运行期间对关卡保存的一次尝试因文件占用失败，失败版本没有替代最终关卡。
- 当前预览 PID 31428，日志已记录 `Game class is BP_DesktopPreviewGameMode_C`、`Load map complete L_CombatLabLite` 和 `Bringing World ... up for play`。持久缓存后的这次启动约 18 秒进入关卡。
- 通过 UE 的 Python 控制台与 Slate tick 延迟捕获两张游戏帧，视觉复核通过：蓝色背景、平整地面、正面红色山门、合理比例的柱子，以及直立并面向出生点的两名 mannequin。最终截图 `Docs/AI/CombatLabPreview.png`；这是简单资产测试场地，未完成正式环境美术。
- `DesktopRuntimeAnimation.json` 记录约 30.16s 与 31.63s 的运行状态，实际 Pawn 为 `BP_DesktopPreviewPawn_C`。两名模型的动画时间从 2.259s 环回到 0.626s，头部世界位置从约 Z144cm 变到 Z160cm，证明待机在运行中持续播放。
- 操作绑定与配置已检查；真实键鼠手感和移动输入由用户试玩确认，未代替人工输入验收。截图与动画观测不代表 VR、导航、战斗或伤害通过。
- 本轮交付暂停在用户测试节点；下一阶段先恢复受支持的 C++ 工具链，再按 M1、CORE-01、ENEMY-01/DIR-01 的依赖顺序接入玩法。

## MSVC 安装完成（2026-10-08）

- 用户明确授权安装兼容 MSVC。下载并验证微软数字签名后，安装 Visual Studio 2022 Build Tools 17.14.37710.0 到 `D:\UEBuildTools2022`，组件为 14.44 x64/x86 编译工具和对应 ATL。
- `vswhere` 确认新实例 isComplete=true、isRebootRequired=false。实际 cl.exe 版本为 19.44.35229，链接器/工具集版本为 14.44.35229，满足本机 UE5.8.2 允许区间。
- 工具集目录族名仍为 `14.44.35207`；这是微软的目录命名。兼容性按编译器实际补丁版本检查，不能依据目录名误判为禁用版本。
- 使用独立临时工程执行 UE `ToolchainProbeEditor Win64 Development -SkipBuild`，退出码 0、Result: Succeeded。UBT 自动选择了 D 盘的新 cl.exe，并使用现有 Windows SDK 10.0.22621.0。
- 本检查生成构建计划，未编译游戏模块。实际游戏源码仍归档待恢复注册；下一步可进入真实 UHT/C++ 编译。
- 安装记录：`MSVCInstallation-2026-10-08.json`；UE 验证日志：`MSVC-UBT-Validation-2026-10-08.txt`。

## 战斗 C++ 模块恢复与编译（2026-10-08）

- 从归档复制回 17 个源码/Target/Build 文件，恢复 `.uproject` 的 `experiment` Runtime 模块注册。归档完整保留；注册前的工程描述备份为 `experiment-before-cpp-2026-10-08.uproject.txt`。
- 修正六个类的导出宏为 `EXPERIMENT_API`，修正 `AIController.h` 路径，并显式包含 `Engine/World.h` 和 `Navigation/PathFollowingComponent.h`。两个 Target 固定 UE5.8 的 `BuildSettingsVersion.V7` 和 `Unreal5_8` include order。
- 首次构建通过 UHT 后，MSVC 对中文 response-file 输出路径发生编码错误。建立英文目录 Junction 分别映射项目和引擎，随后 C++ 编译可正常进行。映射不复制或移动项目/资产；可重复使用入口为 `Build_CombatModule.cmd` / `Build_CombatModule.ps1`。
- 最终 `experimentEditor Win64 Development` 构建退出码 0，`Result: Succeeded`，生成 `Binaries/Win64/UnrealEditor-experiment.dll`、PDB 和模块元数据。使用 MSVC 14.44.35229 / SDK 10.0.22621.0；日志 `BuildLog-CombatModule-2026-10-08.txt`，失败尝试日志单独保留。
- 用 UE 命令行编辑器从原始中文工程路径加载刚编译的模块，退出码 0，报告 0 errors / 0 warnings。六个 `/Script/experiment` 原生类全部加载：战斗身份、攻击定义、结算器、攻击导演、敌人脑组件和敌人 Character。记录 `CombatModuleLoad-2026-10-08.json` 与同名 `.log`；构建摘要 `CombatModuleBuild-2026-10-08.json`。
- 本轮完成源码恢复、Editor target 编译与模块加载。未构建独立 Game target 或打包 EXE；当前地图中的两名 mannequin 仍用于待机预览，尚未接入敌人追击、攻击动画或实际伤害。编译与类加载通过不代表 CORE-01、ENEMY-01/DIR-01 或 VR 玩法验收通过。

## Enemy 剑士动作替换（2026-10-08）

- 用户要求降低 Enemy 动作的夸张程度。工程已包含 `/Game/Animations/Sword/` 下 164 个动画，无需下载新包。
- 在 UE 内读取 8 个候选片段，确认与当前 mannequin 使用同一骨架。选择 `Anim_CSST` 的剑士常规站姿待机，时长约 9.8667s、原速 1.0、循环开启、root 不产生位移。9 个压缩姿势抽样中，头部 Z 范围约 2.673cm；原 ExtremeCombat/Anim_L_Idle 约 26.246cm。抽样数值用于选片，不代表完整逐帧极值。
- 将两名 Enemy 的现用动画从 `ExtremeCombat/Anim_L_Idle` 替换为 `Sword/Anim_CSST`，保存为 `L_CombatLabSword`（12 个 Actor）。原站位、朝向与模型沿用现有 demo；该版本的控件文字同步更新。
- `Run_CombatLab_Demo.ps1` 和工程默认地图现已加载剑士版。当前原有编辑器进程未重载旧关卡；在编辑器里需打开 `L_CombatLabSword`，或使用 demo 入口。
- 新版桌面预览 PID 58460，日志确认剑士地图完成加载。实际采样两名模型均播放 Anim_CSST，动画时间从 0.567s 到 1.941s，头部位置持续变化。两张游戏截图视觉复核通过：直立、落地、站姿稳定，未出现此前的大幅上下摆动。
- 记录：`SwordAnimationCandidates-2026-10-08.json`、`SwordAnimationReplacement-2026-10-08.json`、`SwordRuntimeAnimation-2026-10-08.json` 与 `SwordDemoPreview.png`。当前替换的是 demo 中实际播放的待机表现；剑术移动、斩击、格挡等其他片段尚未接入战斗状态机。

## 用户武侠男模型接入（2026-10-08）

- 收件箱新增 `AssetInbox/武侠男.blend`。检查确认是 Blender 5.1 的压缩文件，含一个约 345,510 面的静态人物和完整内嵌 Color/NormalGL/ORM 贴图，没有骨架、蒙皮或动作。原文件完整保留，SHA256 为 `F503BB1C7FB07BF3D33CEEA90F2F7F207263964635E093943020E890194F31ED`。
- 本机 Blender 4.2 无法读取该格式；使用 Blender 官方 5.1.2 Windows 便携版，校验官方 SHA256 后解压到本任务缓存。未替换原 Blender 安装。
- 为预览制作 23 根基础人形骨骼，将角色规范到约 180cm、减面到 50,000 个三角面，贴图导出为 2K PNG。UE 材质接入 BaseColor、Normal、AO/Roughness/Metallic；OpenGL 法线翻转绿色通道。
- 首次实际游戏帧发现袖口/手腕撕裂，追查到源对象使用四元数旋转，设置 Euler 朝向没有旋转网格数据。已改为直接旋转顶点数据，使手臂与骨骼轴一致；同时将厘米单位烘焙到骨骼和网格，替换为连续空间权重，衣摆/发尾采用平滑绑定遮罩。最终源文件为 `ArtSource/WuxiaMale/WuxiaMaleGame.blend` / `.fbx`；米单位编辑副本 `WuxiaMaleRigged.blend` 同步修正。
- 正式预览资产为 `/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Demo`；早期 `SK_WuxiaMale` 只是未使用的导入试作。创建两套 IK Rig 和 Retargeter，将现有 Sword/Anim_CSST 重定向为 `Animations/Wuxia_Anim_CSST`，长约 9.8667s，循环、原速播放。
- 两名 Enemy 替换后地图保存为 `L_CombatLabWuxia`，12 个 Actor。默认启动地图和 demo 脚本已指向该版本。原 Sword/Lite 地图保留；C++ 模块本轮没有改动。
- 最后一次角色导入与重定向退出码 0，0 errors / 4 warnings（重复单例 retarget op、动画导入依赖、无自定义曲线、覆盖动画时参考收集回退）；关卡构建退出码 0。日志分别为 `ImportWuxiaEnemy-AxisRepair.log`、`BuildWuxiaDemo.log`。
- 最终桌面运行 PID 52244，日志确认新地图加载。`WuxiaRuntimeAnimation-2026-10-08.json` 中，两名角色实际使用新 mesh/animation，时间由 0.909s 增至 2.372s，头部位置随时间变化。`WuxiaDemoPreview.png`、`WuxiaDemoPreview2.png` 的实际游戏帧已查看，角色直立，材质显示完整，手腕/袖口与衣摆不再出现首次导入的撕裂。
- 这是外观与待机预览用的基础绑定，没有手指/面部动作及布料/头发模拟。长袍暂按骨盆面板处理，跑动和斩击需要逐段检查与细调。Enemy 仍为 SkeletalMeshActor；尚未接入追击、攻击、伤害或 VR 双手玩法。本轮停在用户试玩节点。

## Enemy 脸部优化（2026-10-08）

- 按用户要求优化现有角色面部，保留原五官与角色身份。从原始 `.blend` 重建头部，减面时将头部顶点设为保护区。全身三角面从 50,000 增至 65,000；头部前侧统计区域从 3,123 增至 19,745 个三角面（该区域包括头发和耳部，不等同于纯皮肤面数）。顶点从 37,194 增至 43,210。
- 恢复原文件内嵌的 4096px BaseColor/NormalGL/ORM，脸部单独使用 `M_WuxiaMale_Skin`；身体使用已有材质。皮肤金属度 0、镜面参数 0.35、粗糙度 0.45–0.75、AO 0.75–1.0，法线 XY 强度 0.55。没有对贴图进行 AI 重绘或虚假放大。
- 修正下颌至额头的绑定，面部皮肤在头部区域统一跟随 head 骨骼，颈部采用平滑过渡。原骨架、23 根骨骼与 Sword 待机保持兼容，不新增表情骨骼。
- 新模型 `SK_WuxiaMale_Face` 沿用 `SK_WuxiaMale_Demo_Skeleton` 和 `Wuxia_Anim_CSST`，接入两名 Enemy；关卡为 `L_CombatLabWuxiaFace`。原模型和 Wuxia 关卡可用于回退。可编辑源文件及 FBX 位于 `ArtSource/WuxiaMale/FaceOptimization/`。
- 实际游戏近景发现初次皮肤材质缺少 SkeletalMesh usage，产生灰色回退材质；已使用 UE5.8 的 SetBaseMaterialUsage 保存标记。另将现有天空灯改为 Movable，使用引擎 DaylightAmbientCubemap、强度 0.65，改善面部阴影中的可读性。没有增加每个角色的跟随补光灯。
- 中性灯光、相同相机下的 Blender 前后对比已查看：原先额头的折线消失，五官轮廓更连贯。最终真实游戏正面与侧面截图 `EnemyFaceAfterFront.png` / `EnemyFaceAfterThreeQuarter.png` 已查看，皮肤材质正常、阴影半脸可见。游戏前后图包含环境光调整，不能当作仅改变几何的同光照对比。
- 最终材质与环境光保存退出码 0，0 errors / 0 warnings（`FinishWuxiaFace.log`）。最终运行日志没有 Python error 或缺少材质 usage 的警告。头像捕获暂固定动画以比较角度；实测前后版本均为 0.0s（pause 属性更新重置了原本指定的 0.9s），捕获后恢复待机。后续捕获脚本已调整属性写入顺序；本次证据以 `EnemyFaceRuntimeAfter.json` 的实际数值为准。近景不代表全部攻击姿势或 VR 性能验收。
- 默认地图和 `Run_CombatLab_Demo.ps1` 已更新到脸部优化版，运行预览 PID 49712。仍没有眨眼、口型或表情系统；后续与敌人战斗动作一起接入。原始收件箱 `.blend` 未修改。


## Enemy 脚位与足底接触修复（2026-10-09）

- 靴底此前有约三成权重跟随 calf，产生靴子倾斜；低衣摆也混入腿部权重。调整 6,475 个下身顶点的权重：靴底/脚尖跟随同侧 foot，靴筒平滑过渡到 calf，低衣摆跟随 pelvis。保留 65,000 三角面、原脸部几何/材质/UV、23 根骨骼及原始收件箱文件。
- 原重定向资产含 17 个重复操作，新 RTG_Mannequin_WuxiaMale_Feet 使用六个操作、两个 foot goals、两个 limb solvers 与 Floor Constraint。
- 新动画 Wuxia_Idle_Planted 沿用 9.8667s 剑士待机，只修正八根腿/脚骨骼的轨道。脚位使用与骨盆朝向和长袍宽度匹配的站姿，双脚在平地固定接触；每帧用两段骨骼 IK 解膝盖，保留身体起伏。初稿较宽站姿在靴口产生牵拉，最终已收窄并重拍。
- 对保存后的 297 个压缩动画帧计算真实靴底：误差小于 0.0041cm，脚踝漂移小于 0.014cm，鞋底倾角小于 0.035°。上身位置相对接触修正前的差值小于 0.006cm（压缩误差）。指标来自导入后的骨骼姿势及实际靴底顶点，不以脚骨骼高度充当脚底高度。
- 当前关卡 L_CombatLabWuxiaFeet 使用两个 SK_WuxiaMale_Feet；将太阳光设为 Movable，并启用角色动态阴影，增加脚底落地的视觉依据。保存退出码 0、0 errors / 0 warnings。
- UE 实际运行的正面脚部、侧面脚部与全身截图已查看；动画时间持续变化，脚位保持稳定。证据为 EnemyFeetFront.png、EnemyFeetSide.png、EnemyFeetFullBody.png、EnemyFeetRuntime.json 及 EnemyFeetFixDelivery-2026-10-09.json。最终预览 PID 81016；用户原编辑器 PID 46828 未关闭。
- 默认地图与启动脚本已更新。双击 Run_CombatLab_Demo.cmd 可打开最终版本；已打开的旧编辑器需打开 /Game/ReversedScale/Maps/L_CombatLabWuxiaFeet。
- 修正范围是当前平地站立待机；后续移动、攻击和不平地面要分别处理足底接触。本轮没有改变战斗系统或做 VR 设备验收。


## 玩家月曜武器握持与平视视角（2026-10-09）

- 接入用户提供的 Yueyao_Hero_Weapon_Refined_Highlight.blend，原文件未修改；源副本、FBX、贴图与导出脚本保存在 ArtSource/Weapons/Yueyao。刀长约 73.64cm、握柄直径约 2.1cm，152,946 三角面、九个材质槽，保留原玉色、铜饰、皮革、龙纹及非自发光高光设定。
- 导出前将各部件实际用于渲染的 UV 层统一为第零通道，恢复刀面和龙纹护手的原投影。对转换曲线的退化 UV 添加平面坐标，使用 BuiltIn 切线；极细装饰仍有 near-zero tangent 日志，当前材质不使用切线法线贴图，最终画面已查看。
- 新增 ANLDesktopPlayerCharacter，使用 CharacterMovement 落地行走、WASD/鼠标输入、80°视野。沿用项目 MannyXR 右手，将 Grasp 与 IndexCurl 合成静态握持；武器枢轴位于皮革握柄中心，通过 hand_r 骨骼挂接。手部使用棕色手套材质，并接上深色袖口。
- 根据最近 Enemy 的 head 骨骼加校准眼部偏移设置视点，补偿 Character 胶囊与地面的 2cm 间隙；Tick 等待参考 Enemy 骨骼刷新，保留其待机起伏。实际运行的两次高度采样见 PlayerWeaponDelivery-2026-10-09.json。
- 新地图 L_CombatLabYueyao 继承已修正的 Enemy 面部、靴底和 Wuxia_Idle_Planted。新 GameMode 只在该预览关卡启用；原 XR GameMode 与旧地图保留。启动入口 Run_CombatLab_Demo.cmd 和工程默认地图指向新版。
- experimentEditor Win64 Development 编译成功，导入与关卡保存退出码 0。已打开局内画面并查看 YueyaoFirstPerson.png / YueyaoFirstPerson2.png；键盘鼠标实际操作留待用户反馈。本轮提供桌面手持显示与平视视角，未加入挥刀、碰撞伤害或头显追踪。


## 刀身重做：修长单刃（2026-10-09）

- 按用户选择，将宽月牙刀身替换为修长、微弯的单刃刀身。刀身长 62.5cm，根部宽 3.8cm，刀背末端相对根部弯曲 2.5cm；根部厚 6mm，厚度向尖部收薄，刃口双面渐薄。保留完整闭合网格，长度方向法线平滑，刀背/刀面/刃口的转折保持清晰。
- 只替换源文件中的旧刀身对象。原皮革刀柄、铜饰、玉饰、龙纹护手和尾环共 34 个对象，导出前后的评估顶点/面索引/材质名称哈希完全一致。UE 直接复用所有原刀柄材质资产，新刀身使用独立 Steel / Edge / Spine 材质。
- 新刀身约 1,550 三角面，整把武器为 115,902 三角面；旧月牙版本为 152,946。枢轴、hand_r 挂点、手部动作与玩家平视设置保持原值，未改 C++ 源码或关卡。
- 当前 SM_Yueyao_Player 已替换为新版；旧 UE 网格另存为 SM_Yueyao_Player_CrescentBackup_20261009，原始 Highlight.blend 保留。可编辑新源文件位于 ArtSource/Weapons/Yueyao/SlenderBladeRevision/。
- 导入退出码 0，0 errors / 0 warnings。已打开新版 Demo 并查看实际局内截图 YueyaoSlenderFirstPerson.png / YueyaoSlenderFirstPerson2.png，以及 Blender 完整模型图 YueyaoSlenderModel.png。运行采样仍保持 Enemy 眼部与玩家相机等高，具体数值见 SlenderBladeDelivery-2026-10-09.json。等待用户对刀身外观的反馈。


## 2026-10-09 桌面近战试玩模块

依据资料包第 7、9、21、22 节，接通 CORE-01、CORE-02 的生命/暂停部分和 COMBAT-01 桌面输入。
当前地图为 L_CombatLabMelee，使用新单刃刀和修复脚部后的角色。左键驱动可见挥刀轨迹，
刀刃扫掠交给统一结算器，两名静止弟子各 30 生命、近战伤害 30；增加死亡、命中反馈、暂停和 R 原位重置。
Editor Development 已实际编译成功，地图与攻击 Data Asset 已保存。试玩行为等待用户操作确认。
没有新增或运行自动化测试。真实 VR 输入、护势规则、敌人主动攻击、弹丸/反弹和检查点均留待后批。
交付详情见 MeleeLabDelivery-2026-10-09.json；旧状态已备份为 State-before-Melee-2026-10-09.txt。


## 2026-10-11 每刀 10 伤害与 Enemy 受击／死亡动画

按用户要求将 DA_YueyaoMelee 伤害改为 10，训练敌人仍为 30 生命。
比较 3583 动作包中的 10 条候选并渲染实际角色姿态，选择剑士受击 Anim_CS_GH_F_03 与自然倒地 Anim_dEAh_F_04。
重定向到当前 23 骨 Feet mesh：受击烘焙为 0.8 秒，保持稳定站姿的腿部与骨盆；死亡裁去前段停顿，烘焙为 2.8 秒并修正落地轨迹。
真实非致命扣血触发受击，致命扣血触发单次死亡并保留尸体。暂停与 R 重置沿用游戏时间，镜头过滤受击／死亡的眼高参考。
Editor Development 已编译成功，新动画和地图引用已保存；初始运行配置记录见 EnemyReactionsRuntimeScene-2026-10-11.json。
未新增或运行自动化测试，三次挥刀、暂停和重置的手动验收等待用户试玩。敌人主动攻击与导航仍未接入。


## 2026-10-15 SteamVR 手柄输入与真实皮肤手部

- 新增 NLVRPlayerCharacter / NLVRGameMode 和独立 L_CombatLabVR。左摇杆按头部朝向移动，右摇杆每次转向30度，左右手柄追踪手部和武器。真实挥刀沿用统一结算器，每刀10伤害；刀气15、左扳机护心镜格挡。
- 使用 OpenXR Enhanced Input，13个动作与53条有效映射覆盖 Index、Touch、Vive、WMR、PICO、HP；Vive/WMR 触控板按下后移动/转向。运行时状态与按钮说明改为立体文字。实际 HMD 高度直接取设备地面坐标。
- 新启动器 Run_VR_Demo.cmd 通过本次 UE 子进程环境变量指定 SteamVR OpenXR，不修改系统默认运行时。专用地图沿用两波混合敌人，使用独立检查点上下文；桌面入口保留。
- 将机械手表面改为连续皮肤，补掌丘、指节、肌腱、低幅掌纹与短指甲，三轮调整指甲贴合后再平滑手腕局部折痕。每手30720三角、两材质槽；皮肤有线性顶点肤色及1024微法线/粗糙度贴图。左手沿用镜像握镜姿态。
- 完整47骨父级和参考姿态保持兼容；原手部网格、骨架与握持动画文件哈希不变。新模型保留自身皮肤/指甲材质，旧手套仅作为旧模型回退。
- Editor Development 编译成功；输入、地图、网格及材质已保存，着色器无编译错误。已查看 Blender 三视图和实际局内 Ready 初始握持截图；生命/护势100，敌人0，临时外观呈现已恢复。
- 未添加或运行测试，也没有发送移动/攻击/格挡输入或合成控制器姿态。真实 SteamVR 手柄、挥剑命中、握持偏移及帧率仍需用户试玩。交付记录 VRHandsDelivery-2026-10-15.json，快照 Deliveries/VRHands_20261015/Manifest.json。


## 2026-10-16：A武器与VR握持/入场修复

- 用户从真实模型组合预览选定A，已接入主角右手：03剑身、03护手、04握柄、03剑首；双刃直剑，整体78.314cm，1594三角面。
- 原材质和UV保留，握柄中心与旧手部挂点对齐；右手整体转正，锋刃朝前。命中采样已按新直剑长度更新，近战伤害仍为10。
- VR设备、映射、存档连续就绪3秒后自动进入首波；入场/恢复时对齐头部水平朝向；取消或重试后仍可用A/菜单手动开始。
- 用户日志的NavigationFailed来自第一次移动及重定位失败就隐藏敌人；现增加导航就绪等待和真正的间隔重试，并重新保存VR地图导航数据。
- 暂停时可以使用手柄重试。编译与资产保存成功，初始桌面持握呈现已检查；实际VR移动、挥剑、入场和导航仍待用户试玩。
- 报告：VRGripSwordADelivery-2026-10-16.json；试玩入口：Run_VR_Demo.cmd。旧月曜模型保留，项目仍需本机UE5.8运行。


## 2026-10-16：护心镜建模精修

- 本批精修护心镜几何：龙纹浮雕、金属边框、背柄皮革包覆和固定件；细项与面数见 ShieldModelDelivery-2026-10-16.json。
- 可编辑 Blender 文件和 FBX 位于 ArtSource/DragonShield/ModelRefinement_20261016，原始模型保留，UE 继续使用原 SM_DragonShield 资产路径及写实材质。
- 保持46厘米尺寸、原点与左手握持锚点，四级LOD和原格挡碰撞归属。已保存资产并采集初始持握、正面与背面画面。
- 本批未改动原生代码，无需重新编译；没有添加或运行测试。头显中的近距离观感与握持仍待用户试玩确认。
- 试玩入口：Run_VR_Demo.cmd；本批备份：Deliveries/BeforeShieldModel_20261016；增量交付：Deliveries/ShieldModelRefinement_20261016。
