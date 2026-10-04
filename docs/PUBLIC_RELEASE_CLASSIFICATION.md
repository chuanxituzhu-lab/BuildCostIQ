# GitHub 源码更新公开分类记录

状态：Public 源码更新；分类范围仅限本记录列出的源代码、界面资产、通用文档、构建脚本和合成测试。用户明确要求更新公开的 BuildCostIQ GitHub 仓库；逐项检查后，这些条目不含真实项目资料、项目账本、安装日志、凭证或本机绝对路径。

## 本次列为 Public 的文件

- adapters/role_intelligence.py
- tests/test_role_intelligence.py

- `.gitignore`
- `ARCHITECTURE.md`
- `README.md`
- `pyproject.toml`
- `adapters/auth.py`
- `adapters/workspace.py`
- `core/execution_ledger.py`
- `domains/business_workflows.py`
- `docs/NEW_01_09.md`
- `docs/PUBLIC_RELEASE_CLASSIFICATION.md`
- `gui/server.py`
- `gui/static/app.js`
- `gui/static/index.html`
- `gui/static/styles.css`
- `gui/static/sayelf-logo.png`
- `gui/static/sayelf-logo.ico`
- `installer/README.md`
- `installer/windows/INSTALL.md`
- `installer/windows/build.ps1`
- `installer/windows/configure.ps1`
- `installer/windows/delivery_check.py`
- `installer/windows/initialize.py`
- `installer/windows/launch.py`
- `installer/windows/package-delivery.py`
- `installer/windows/project-server.iss`
- `installer/windows/smoke.py`
- `installer/windows/test_delivery_check.py`
- `installer/windows/test-installed.ps1`
- `installer/windows/languages/ChineseSimplified.isl`
- `installer/windows/languages/ChineseSimplified-MIT-LICENSE.txt`
- `tests/test_auth.py`
- `tests/test_role_ui_boundaries.py`
- `tests/test_web.py`
- `tests/test_agent_ops_api.py`
- `tests/test_business_workflows.py`
- `tests/test_business_workflows_api.py`
- `tests/test_execution_ledger.py`

## 不公开的内容

项目运行数据、真实图纸/合同/投标/结算/试验资料、账本、账号配置、安装/服务日志、机器专属验证回执、临时构建目录、工作区归档和 Windows 安装器二进制均不属于本次源码提交。二进制仅留在本机交付目录。

## 发布前检查

- 仅按上表精确暂存，不包含其他未分类工作树文件。
- 暂存差异复核项目代码、文档、测试和 GUI 资源；扫描凭证标记、本机用户目录与私有数据目录。
- 先运行与功能相关的回归测试及安装包 smoke；保留构建收据在本地交付目录。
- 若新增文件未列入上表，默认不进入此公开更新。
