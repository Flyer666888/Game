# UE 编辑器自动化能力清单

核查日期：2026-10-08
引擎：Unreal Engine 5.8.2  
工程：`experiment.uproject`

## 当前连接状态

| 项目 | 证据 | 结果 |
|---|---|---|
| 当前 Codex 工具清单中有 Unreal 专用 MCP | 对运行时暴露的 tool name/description 做 `unreal`、`UE5`、`editor` 检索 | 未发现 Unreal 编辑器读写/资产操作接口 |
| 项目已启用 Unreal MCP 插件 | `experiment.uproject` 插件列表 | 未配置 |
| UE 安装内的 MCP 相关插件 | `Engine/Plugins/Experimental/Toolsets/MCPClientToolset/MCPClientToolset.uplugin` | 存在 Epic `MCP Client Toolset`；描述为连接本地/私有 MCP server 的 adapter；它本身不提供 UE 编辑器 MCP server |
| MCP server endpoint / auth | 未在工程配置与当前会话发现 | 未设置，未连接 |
| Python Editor Script Plugin | UE PythonScriptCommandlet 成功构建、保存并重新读取 `L_CombatLabLite` | 已验证可用，构建退出码 0，审计退出码 0；无需依靠 MCP |
| Editor Scripting Utilities / Editor subsystems | `EditorAssetLibrary`、`EditorActorSubsystem`、`LevelEditorSubsystem` 实际运行 | 已验证资产和关卡读写；使用子系统入口优先 |

## 已核实的 MCP 客户端配置能力

安装版 MCP Client Toolset 的设置结构支持服务器名称、说明、URL、Bearer token 或 OAuth2、legacy SSE 或 Streamable HTTP。启动时它尝试连接所配置的 server 并把工具注册进 Toolset Registry。项目尚无 endpoint、凭据或服务端，因此不能做真实 schema discovery、读写探针，也不能声称 MCP 已接通。

## 读写验证

- MCP discovery：`NotRun`（无 server endpoint）。
- MCP editor read/write probe：`NotRun`（无连接与可用 schema）。
- Python editor read/write probe：`Passed`，脚本见 `Saved/Scripts/build_desktop_lab.py`，实际报告见 `Docs/AI/CombatLabLiteBuild.json` 与 `DesktopPreviewAudit.json`。该能力不等同于官方 MCP 连接验收。

## 安全边界

- 不凭印象编造工具名或 schema。
- 只在取得真实 MCP server endpoint、认证方式和可见 tools/list 后，串行做一个可回滚的资产读写验证。
- 在此之前可继续检查源码和配置；如需编辑器资产自动化，优先评估 UE Python Editor Script Plugin，但须启用并验证后才记录为可用能力。

## 下一步

1. 取得官方 Unreal MCP server 的安装/启动入口和连接 endpoint，或确认此 UE 5.8 安装使用 MCP Client Toolset 的方法。
2. 获取当前会话能访问该 server 的 MCP connector/tool provider。
3. 保存真实 tools/schema、连接日志和一项可回滚读写结果。
