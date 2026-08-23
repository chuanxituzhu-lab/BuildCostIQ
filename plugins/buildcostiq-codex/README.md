# BuildCostIQ Codex 本地插件

`buildcostiq-codex` 是 BuildCostIQ 的本地插件包：用一个轻量的 MCP stdio 进程复用现有 Core、P01–P09、岗位权限、部署/存储适配层和 `http://127.0.0.1:8787/` WebUI。它没有自己的数据库、金额账或账号体系，也不要求 OpenAI API Key。

## 包含内容

- `.codex-plugin/plugin.json`：插件元数据；
- `.mcp.json`：本地 stdio 启动配置；
- `mcp_server.py`：无第三方依赖的 JSON-RPC MCP bridge；
- `skills/municipal-cost-workflow/SKILL.md`：按岗位契约执行工作的 Skill。

## 本地使用

1. 确保仓库依赖已经安装，并确认 WebUI 能启动。
2. 将这个目录作为本地 Codex 插件目录加载，或在其他 MCP 客户端中使用 `.mcp.json` 的 `buildcostiq-local` 配置。
3. MCP 客户端启动前设置：

   ```powershell
   $env:BUILDCOSTIQ_PROJECT_ROOT = 'F:\造价数字化BuildCostIQ'
   $env:BUILDCOSTIQ_MCP_ACTOR = '<本地登记人员的登录名或 id>'
   python -u F:\造价数字化BuildCostIQ\plugins\buildcostiq-codex\mcp_server.py
   ```

   如果不设置 `BUILDCOSTIQ_PROJECT_ROOT`，bridge 会从自身目录向上寻找 `pyproject.toml`；如果不设置 `BUILDCOSTIQ_MCP_ACTOR`，只能读取公开岗位契约和健康状态，不能读取项目资料。

4. 首次使用按顺序调用岗位契约、项目工作面，再准备成果。写入工具要求 `confirm=true`，这是对人工确认的第二道保护。

## 暴露的 MCP 工具

| 工具 | 用途 | 写入 |
| --- | --- | --- |
| `buildcostiq_health` | 本地服务、存储边界和 WebUI 地址 | 否 |
| `buildcostiq_get_role_workbench_contract` | 岗位字段、成果和交接契约 | 否 |
| `buildcostiq_get_line_contracts` | 生产线、技术线、造价线协同契约 | 否 |
| `buildcostiq_get_workspace_snapshot` | 当前岗位可见项目工作面和 P09 派生摘要 | 否 |
| `buildcostiq_get_role_work_products` | 当前岗位自己的及待接收成果 | 否 |
| `buildcostiq_submit_role_work_product` | 保存已确认的岗位成果 | 是（需 `confirm=true`） |
| `buildcostiq_get_p09_summary` | 项目经理/造价经理读取 P09 派生成果经营 | 否 |

MCP stdout 只输出 JSON-RPC；诊断写入 stderr，便于 Codex、ChatGPT 或其他 MCP 客户端直接复用。远程 HTTP/OAuth 适配不放进本地包，后续可以在适配层增加，不改变 Core 和本地数据边界。
