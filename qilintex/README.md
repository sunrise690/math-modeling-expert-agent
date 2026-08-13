# 数模工作台前端与协作服务

这里承载数模工作台的唯一前端与协作服务。数模 Agent 和 QilinTeX 不拆成两个前端：同一个 React 客户端以同一项目为上下文，提供“建模 Agent”和“QilinTeX”两个工作区，并共享登录、成员、文档与产物。目录同时包含 Yjs 实时协作服务、项目 API、Windows Electron 本机运行器、Capacitor Android/iOS 配置，以及桌面应用内更新机制。

## 当前可运行能力

- 同一项目内直接切换建模 Agent 与 QilinTeX，不打开第二个应用或站点。
- 多人共同编辑同一个 `.tex` 文档，基于 Yjs CRDT 同步并显示在线协作者。
- 项目创建、项目列表、好友搜索、好友申请与接受。
- 内部团队口令登录：成员首次填写名称和口令，之后同一设备自动保持登录；不依赖 QQ/微信审核。
- AI 侧栏调用当前电脑的本机数模 Agent，可选择自动、建模、整题交付、论文和质检模式，并回传质量评分与可下载产物；Codex 与各类 API 均使用当前电脑用户自己的配置。
- 服务端调用 Tectonic/latexmk 编译 PDF；未安装编译器时返回明确诊断。
- Electron Windows 客户端检查、下载、安装更新；Web 端提供刷新更新；Android/iOS 走应用商店更新。
- 同一套前端代码可构建 Web、Windows、Android 与 iOS。

## 本地启动

1. 在任意位置克隆或解压仓库，不需要复刻开发者目录结构。
2. 在仓库根目录执行 `pnpm setup`；它安装前端依赖，并自动创建仓库相对的 `.runtime/python` 与 Python 依赖。
3. 本地开发可直接使用默认值；需要配置 Provider 或团队访问时，把根目录 `.env.example` 复制为 `.env`。`qilintex/.env` 只作为协作服务的可选覆盖层。
4. 统一 Web 工作台：在根目录执行 `pnpm dev`。脚本从自身位置定位仓库，同时启动数模 Agent、协作服务和 React 前端。
5. Windows 桌面调试：在根目录执行 `pnpm dev:desktop`。该命令同样会启动数模 Agent。
6. Windows 安装器和便携版仍在 `qilintex/` 执行 `pnpm build:win`。

用户只需打开 Web `http://localhost:5173`。内部地址为 REST API `http://localhost:4318`、协作 WebSocket `ws://localhost:4319` 和数模 Agent API `http://127.0.0.1:8765`。

## Ubuntu 云服务器部署

`deploy/` 提供 Ubuntu 24.04 + systemd + Caddy 的部署基线。发布包可解压到任意目录，脚本会从自身位置推导 `APP_ROOT`：

```bash
cd <解压后的项目目录>
sudo bash qilintex/deploy/bootstrap.sh
PUBLIC_HOST=example.com bash qilintex/deploy/configure-server.sh
```

如需自定义安装、数据或配置目录，可显式设置 `APP_ROOT`、`DATA_ROOT`、`CONFIG_ROOT`；默认值不包含任何开发者个人路径。配置脚本会构建项目并安装 `qilintex.service`；服务器只负责账号、项目、LaTeX 编译和多人协作。

`configure-server.sh` 会生成强随机会话密钥和团队访问码，关闭开发登录，并把生产环境写入 `/etc/qilintex/qilintex.env`。首次部署可先用服务器公网 IP 验收；正式使用应把 `PUBLIC_HOST` 设置为已解析域名，并将 Caddy 入口升级为 HTTPS/WSS。

生产端到端验收需要显式提供地址与临时团队码：

```bash
BASE_URL=https://example.com \
COLLAB_URL=wss://example.com/collab \
TEAM_ACCESS_CODE='临时验收码' \
node qilintex/apps/client/scripts/verify-production.mjs
```

## App、本机 Agent 与网页快捷入口

Windows App 是完整入口。它打开同一个在线工作台，并自动启动只监听 `127.0.0.1:8765` 的本机数模 Agent。Codex 浏览器登录在用户电脑上完成；模型 Provider、API Base URL、API Key、题目附件、运行记录和产物均属于当前系统用户，不会上传给协作服务器。Windows 上的 API 密钥使用 DPAPI 加密保存。

网页端是纯在线工作区，可随时登录、查看项目、编辑 LaTeX 和参与实时协作，不展示客户端安装包、下载浮条或桌面推广。如果同一台电脑已有可信本机运行器，网页可通过受限本机通道复用该电脑的 Codex 与 API；没有本机运行器时，只如实标记本机 Agent 未连接，不退回服务器共享账号。

每台电脑安装 App 后都可以登录同一个在线账号接手项目，无需下载源码、安装 Python 或复刻任何开发者目录。项目与协作状态在服务器同步，本机模型配置则在各电脑之间相互隔离。

Windows 构建命令：

```bash
pnpm --dir qilintex build:win
```

构建脚本会准备独立 Python/Codex 运行时，并在 `qilintex/release/` 生成 NSIS 安装版和便携版。服务器部署不安装数模 Agent，也不需要配置 OpenAI 或其他模型密钥。

## 内部团队登录

在 `.env` 中设置 `TEAM_NAME` 和 `TEAM_ACCESS_CODE`。团队成员只需输入自己的名称和共享口令；客户端会生成本机随机身份并保存 30 天会话，团队口令不会写入浏览器存储。服务端会限制连续错误口令尝试。开发环境未设置口令时允许直接输入名称进入，生产环境未设置口令时团队登录会自动关闭。

团队登录和 QQ/微信 OAuth 属于两个独立登录域：分别使用 `tg_team_session` / `tg_oauth_session` HttpOnly Cookie 和独立的客户端 token 存储。JWT 会记录登录域，服务端拒绝把团队 token 用到 OAuth 域（反向亦然）；退出一种登录方式不会清理另一种方式的会话。

在局域网或公网提供给其他成员时，把 `CLIENT_URLS` 设置为允许访问的前端地址列表（逗号分隔，第一个地址用于生成邀请链接）。同源 Web 部署会自动使用当前站点的 `/api`、`/auth` 和 `/collab`，无需写死主机地址；仅当前端与 API 不同源时，才在构建前设置 `QILINTEX_CLIENT_API_URL` 和 `QILINTEX_CLIENT_COLLAB_URL`。生产环境应使用 HTTPS/WSS，并更换强随机 `SESSION_SECRET` 与团队口令。

## OAuth 配置

QQ/微信正式登录不是只填一个按钮即可完成：需要分别在 QQ 互联、微信开放平台创建并审核网站/移动应用，配置回调域名与 Universal Link/应用签名。把平台颁发的 AppID、Secret 和回调地址写入服务端 `.env`，密钥不得打入 Electron、APK 或 IPA。

桌面 OAuth 使用一次性 ticket + `tonggaotex://auth` 自定义协议回到应用；Web 使用 OAuth 登录域专属的 HttpOnly 会话 Cookie。移动端发布时应把同一逻辑替换为平台官方原生 SDK，以满足商店和开放平台审核要求。

## 发布与更新

- Windows：`release/` 中生成 NSIS 安装器和便携 `.exe`。生产发布前必须配置代码签名证书与 HTTPS `UPDATE_URL`，并一起上传 `latest.yml` 和安装包。
- Android：安装 JDK 17 与 Android Studio 后，在 `apps/client` 执行 `pnpm mobile:add:android`、`pnpm mobile:sync`，再用 Android Studio 生成签名 AAB。
- iOS：只能在 macOS + Xcode 上执行 `pnpm mobile:add:ios`、`pnpm mobile:sync` 并完成签名归档。
- Web：部署 `apps/client/dist`，并把 API/协作地址配置为 HTTPS/WSS。

Android/iOS 的应用二进制更新遵循商店发布流程；应用启动后会读取 `/updates/latest`，应用内可检查版本、展示更新说明并跳转商店。Windows 支持应用内下载并重启安装。Web 使用 Service Worker 在新版本就绪后提示刷新。

本地 Windows 若因网络无法下载 NSIS 组件，可执行 `electron-builder --win dir --x64` 生成解包目录，再编译 `apps/desktop/launcher/Program.cs`。解包目录中应通过“Qilintex 启动器.exe”启动；GitHub Actions 会在 Windows 云端生成标准安装器。

## 上线前必须补齐

- 把 JSON 文件存储替换为 PostgreSQL，好友关系和项目成员关系增加唯一索引与事务。
- 把项目权限变更、邀请使用和协作连接写入可检索的审计日志，并增加集中式会话吊销能力。
- 将协作文档存储迁移至 PostgreSQL/S3，并设置备份、快照和历史版本。
- 把 TeX 编译放进无网络、限 CPU/内存/时长的隔离容器；绝不能在主 API 进程中直接编译不受信任的 TeX。
- 接入对象存储、病毒扫描、限流、审计日志、内容合规与隐私政策。
- 配置 Windows/macOS 代码签名、Apple Developer、Google Play、国内 Android 渠道，以及 QQ/微信应用审核材料。
