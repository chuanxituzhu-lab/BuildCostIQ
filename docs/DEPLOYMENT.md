# BuildCostIQ 部署与存储

## 推荐拓扑

```text
岗位电脑（浏览器）
        ↓ 局域网 / VPN
中央 BuildCostIQ WebUI/API
        ↓
中央数据根目录 + 独立备份目录
```

项目部多台电脑只访问中央 WebUI，不各自启动一套正式服务，也不直接修改共享文件夹中的 JSON 文件。

## 中央节点启动

Windows 示例：

```powershell
buildcostiq-web `
  --deployment-mode central `
  --node-id project-server-01 `
  --host 0.0.0.0 `
  --port 8787 `
  --data-root D:\BuildCostIQData `
  --backup-root E:\BuildCostIQBackups
```

岗位电脑打开：

```text
http://项目服务器局域网地址:8787/
```

### 岗位邀请与浏览器入口

项目经理（或已获授权的行政人员）在“人员管理”中选择岗位并生成项目邀请链接。链接只返回一次、默认 72 小时有效，可撤销；岗位人员打开链接后设置或验证自己的登录密码，系统把账号加入该项目名册。登录后只显示该岗位的 WebUI，不需要在每台岗位电脑安装 BuildCostIQ。岗位人员可在浏览器中将当前链接创建为桌面快捷方式；链接指向中央节点，数据仍写入同一个项目底座。人员离职时只需在当前项目撤销成员或更换姓名，原 `user_id`、审计和成果不丢失。

邀请接口：

```text
POST /api/personnel/invites          # 项目经理/授权行政人员生成
GET  /api/personnel/invites          # 查看当前项目邀请（不返回 token）
POST /api/personnel/invites/revoke   # 撤销尚未接受的邀请
POST /api/invite/accept              # 岗位人员接受一次性邀请
```

原始 token 只保存在邀请链接和服务端哈希中；接受、撤销、过期和项目绑定均写入人员审计。

仅在项目内网或受控 VPN 使用；跨出可信网络时，应增加防火墙和 TLS/反向代理。

## 数据位置

`--data-root D:\BuildCostIQData` 会形成：

```text
D:\BuildCostIQData\
├─ projects\   项目状态、P01–P08、Core Event、协同和审计
├─ sources\    按内容哈希保存的原始文件
├─ archive\    项目/分类可读归档副本
├─ basis\      政策、定额、价格和外部依据目录
├─ auth\       用户、岗位、项目成员和授权
├─ backups\    备份输出（也可用 --backup-root 指向另一块磁盘）
└─ locks\      项目级并发写入锁
```

GitHub 只保存代码和文档，不保存上述运行数据。备份目录只用于恢复，不作为实时数据库。

## 一致性规则

- 同一项目的读改写由项目锁串行化；每次保存递增 `project.revision`。
- 项目、事件、证据和审计都保留 `project_id`、永久标识和历史，不使用最后写入覆盖专业事实。
- 共享文件夹只能作为受控备份或交换位置，不能作为多个 WebUI 进程的实时工作区。
- `edge` 只表示未来可接入的草稿/同步节点，不具备最终数据权威；断网数据恢复必须回到中央服务并经过版本和人工冲突检查。
- 专业冲突按责任线人工确认：技术负责人确认技术事实，生产经理确认生产事实，造价经理确认商业事实，项目经理处理跨线决策。

## 检查接口

```text
GET /api/health
GET /api/deployment
```

`/api/deployment` 返回节点模式、数据权威归属、逻辑存储区和一致性策略，不返回绝对物理路径。
