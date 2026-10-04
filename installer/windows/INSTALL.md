# BuildCostIQ Project Server v0.8.0-rc9 x64

仅一个施工项目部。复用现有 JSON 文件型存储；无需目标机预装 Python、Node 或 PostgreSQL。

当前包为 v0.8.0-rc9 服务端安装器，包含 01–05、07–09 的单项目人工业务流程运行时，以及 S06 审批、验收、事件账本重放和岗位交接。它不包含自动造价判断、自动提量或实体质量自动判定；这些专业结论仍由人员完成。Windows 管理员实际安装、服务重启、升级和卸载保留数据仍须在目标 Windows 环境验证；构建机冒烟通过不能代替这些验证。

产品标识使用 SAYELF 山野精灵 Logo，并随安装包用于 WebUI 页眉、浏览器标签、开始菜单快捷方式、安装器和卸载项。
安装向导固定使用简体中文；标准向导文字复用项目内的 `languages/ChineseSimplified.isl`，无需目标机安装语言包。翻译来源及许可见该目录中的许可文件，构建后随程序安装到 `licenses` 子目录。

## 构建

构建机需要现有 .venv Python，以及官方 Inno Setup 6.5 或更高版本。
编译器存在性在下载和运行包修改前检查。中断后用 `-Resume`；部分依赖目录无完成标记时拒绝继续。
运行 `installer/windows/build.ps1 -Compiler <ISCC.exe完整路径>`。
构建从 python.org、PyPI、github.com/winsw 下载公开运行时及依赖，不上传本地仓库或数据。
产物在 dist/windows。嵌入 Python 3.12.10 x64、依赖锁定清单及 SHA256 payload 清单。
复制 core/plugins/adapters/gui/domains、Python 嵌入运行时、已审核依赖与安装脚本；不复制其他构建工作区、fixtures、.git、凭证或项目数据。
重新构建必须使用新的 work/windows-build，保留旧构建用于回滚。

## 安装

以管理员权限运行安装器。程序安装于 C:\Program Files\BuildCostIQ。
首次安装向导使用简体中文，仅填写项目名称、编码、货币、IANA 时区、管理员账号/密码（至少8位，可含字母和符号）、数据及备份目录。
项目编码限字母、数字、下划线、短横线。货币为三字母大写代码。
数据默认 D:\BuildCostIQ\Data；无 D 盘则 ProgramData\BuildCostIQ\Data。
备份默认同级 Backups，必须与数据目录互不包含。该目录仅为现有备份功能的目的地，并非自动定时备份保证。
货币/时区为安装元数据，现有 rc9 计算和时间戳行为不因该字段自动改变。
服务 BuildCostIQProjectServer 以 LocalService 自动启动，异常退出10秒后重启。
日志位于 ProgramData\BuildCostIQ\logs；配置 server.json 无明文密码。如配置或健康检查失败，请查看 ProgramData\BuildCostIQ\logs\install.log；日志记录失败阶段与原因，不记录管理员密码。安装器兼容 Windows 自带 PowerShell 的 UTF-8 输入格式。
安装完成检查 http://127.0.0.1:8787/api/health，成功后打开浏览器。
局域网终端浏览器访问 http://服务器地址:8787；防火墙限 Private/LocalSubnet。
现有 rc9 使用 HTTP，部署在可信项目部局域网，不直接暴露公网。

## 升级、修复、卸载

固定 AppId，升级/修复先停止服务，再更新程序；沿用 ProgramData 中配置，跳过首次初始化。
卸载停止并删除服务及其防火墙规则，仅卸载程序；数据、备份、配置、日志保留。
重新安装保留已有配置。不要删除配置以尝试重置管理员。
升级前停止服务并复制完整数据目录到独立备份；旧程序安装器与数据备份配套回滚。
无自动数据迁移、失败安装事务回滚或强制清理用户数据。

## 验证

构建机执行 `installer/windows/build.ps1`；构建后 smoke 使用临时合成项目，验证初始化、密码不明文、重复初始化拒绝、S01–S09 流程目录/API、中文工作台入口、S06 运行事件哈希链/状态重放、受登录/权限/项目名册保护的 Agent Ops 计划接口、`READY` 计划语义、嵌入运行时和健康端点。
传入第三个参数 `dist/windows` 可保存绑定运行包指纹的 smoke-result 和 manifest，并确认已有依赖可复用。
`package-delivery.py <输出目录>` 仅归档通过同一指纹验证的运行包；已有 ZIP 在指纹及自身 SHA256 匹配时复用。
实际安装还需验证：服务 Automatic/Running、重启恢复、升级保留账号和项目、卸载保留数据。
管理员安装后运行 `installer/windows/test-installed.ps1 -RestartService`，检查服务身份、自动启动、API、重启前后账号/项目文件校验值。
该脚本不进行真实开机重启、升级或卸载，这些动作仍需分别实测。
未实际执行的步骤必须在验证报告标为未验证，不能将构建成功等同安装成功。

## 桌面连接器下一步入口

后续独立制作 `BuildCostIQ-DesktopConnector-x64.exe`，先复核 CAD、SketchUp、广联达、Office/WPS 工作站的实际接入边界和用户流程，再实现必要连接器。
本包不安装 CAD、SketchUp、广联达、Office/WPS 适配器，不引入 Enterprise、多项目或ERP。
