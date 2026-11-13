# NI LIN1.0（逆鳞）

基于 Unreal Engine 5.8 的 VR 动作游戏项目（OpenXR / PICO）。

## 项目结构

| 目录 | 说明 |
| --- | --- |
| `experiment/` | UE 5.8 主工程（C++ 源码、关卡、美术资源、设计文档） |
| `InklineRooftops/` | Unity 原型工程 |
| `BrowserPreview/` | 浏览器试玩预览 |
| `Evidence/` | 编译与运行验证记录 |
| `视频捕捉合集/` | 动作捕捉 / 表情识别 Web 工具集合 |
| `Docs/` | 设计文档与玩法回顾录像（位于 `experiment/Docs/`） |
| `Deliveries/` | 美术资产交付记录（位于 `experiment/Deliveries/`） |

## 打开主工程

1. 安装 Unreal Engine 5.8。
2. 右键 `experiment/experiment.uproject` → Generate Visual Studio project files。
3. 用 `experiment.sln` 编译后打开工程。

## 未入库目录说明（体积超限或可再生）

以下目录因超过 GitHub 单文件 100MB 限制或属可再生缓存，未上传：

- `experiment/AssetInbox/` — 市场素材原始包（约 25GB）
- `experiment/Content/AsianTemple/` — 市场示例场景（约 2.4GB）
- `experiment/Intermediate/`、`Binaries/`、`Saved/`、`DerivedDataCache/` — 编译缓存与自动保存
- `视频捕捉合集/runtime/` — 内置 Node.js 运行时（可用 `install-nodejs.bat` 重新获取）
