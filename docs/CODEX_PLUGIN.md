# BuildCostIQ Codex 插件与 MCP 边界

从 `v0.8.0-rc5` 起，仓库内提供 `plugins/buildcostiq-codex` 本地插件包。它是一个薄适配层：

```text
Codex / 其他 MCP 客户端
        │ stdio JSON-RPC
        ▼
buildcostiq-codex bridge + municipal-cost-workflow Skill
        │ 复用
        ▼
现有权限 → WebUI 服务边界 → LocalProjectWorkspace / DeploymentStorageAdapter
        │
        ▼
Core + P01–P09 + Event / Evidence / Outcome
```

## 设计决策

- **不扩 Core**：插件只调用现有服务私有边界和适配器，不新增 P10，也不维护第二金额事实源。
- **岗位隔离**：身份解析使用 `LocalAuthStore`，项目成员使用现有项目 roster，成果过滤沿用 WebUI 的岗位权限和敏感金额脱敏。
- **人工确认**：所有成果写入要求 MCP 参数 `confirm=true`；决策仍由人确认。
- **WebUI 保留**：插件返回当前 WebUI 地址用于可视化复核，不替代页面。
- **平台可迁移**：本地平台只需要启动同一个 stdio 命令；未来 HTTP/OAuth 只增加远程适配器，不改变工具契约。

## 不使用 API Key 的条件

本地 MCP 进程直接访问本地 BuildCostIQ 运行时和本地账号，因此不需要 OpenAI API Key。OCR 等已有可选外部适配器仍按各自环境变量配置；它们不是插件运行前提。

## 安全边界

请不要把密码、令牌、私钥或 `runtime/` 数据提交到仓库。`BUILDCOSTIQ_MCP_ACTOR` 只填写本地已登记人员的 id 或登录名；bridge 不接受通过工具参数伪造岗位。跨机器使用时，应把 MCP bridge 放在受控服务端并增加 HTTPS/OAuth 适配，而不是把共享文件夹当作数据库。
