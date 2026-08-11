# Qilintex

Qilintex 是一个跨端多人 LaTeX 工作台 MVP。当前仓库包含共享 React 客户端、Yjs 实时协作服务、免审核的内部团队登录、好友与项目 API、OpenAI Responses API 助手、Windows Electron 封装、Capacitor Android/iOS 配置，以及桌面应用内更新机制。

## 当前可运行能力

- 多人共同编辑同一个 `.tex` 文档，基于 Yjs CRDT 同步并显示在线协作者。
- 项目创建、项目列表、好友搜索、好友申请与接受。
- 内部团队口令登录：成员首次填写名称和口令，之后同一设备自动保持登录；不依赖 QQ/微信审核。
- AI 侧栏通过服务端 OpenAI Responses API 读取当前文档并回答或给出可插入的 LaTeX；绘图请求会按阶段协调代码绘图、结构图与生成式图片，并回传可预览/下载的图形产物。
- 服务端调用 Tectonic/latexmk 编译 PDF；未安装编译器时返回明确诊断。
- Electron Windows 客户端检查、下载、安装更新；Web 端提供刷新更新；Android/iOS 走应用商店更新。
- 同一套前端代码可构建 Web、Windows、Android 与 iOS。

## 本地启动

1. 复制 `.env.example` 为 `.env`，至少修改 `SESSION_SECRET`。
2. 安装依赖：`pnpm install`。
3. Web + 服务端：`pnpm dev`。
4. Windows 桌面调试：`pnpm dev:desktop`。
5. 构建 Windows 安装器和便携版：`pnpm build:win`。

默认地址：Web `http://localhost:5173`、REST API `http://localhost:4318`、协作 WebSocket `ws://localhost:4319`。

## Ubuntu 云服务器部署

`deploy/` 提供 Ubuntu 24.04 + systemd + Caddy 的部署基线。发布包解压到 `/opt/qilintex/releases/<版本>` 并让 `/opt/qilintex/current` 指向该目录后，可执行：

```bash
cd /opt/qilintex/current
sudo bash deploy/bootstrap.sh
PUBLIC_HOST=example.com bash deploy/configure-server.sh
```

`configure-server.sh` 会生成强随机会话密钥和团队访问码，关闭开发登录，并把生产环境写入 `/etc/qilintex/qilintex.env`。首次部署可先用服务器公网 IP 验收；正式使用应把 `PUBLIC_HOST` 设置为已解析域名，并将 Caddy 入口升级为 HTTPS/WSS。

生产端到端验收需要显式提供地址与临时团队码：

```bash
BASE_URL=https://example.com \
COLLAB_URL=wss://example.com/collab \
TEAM_ACCESS_CODE='临时验收码' \
node apps/client/scripts/verify-production.mjs
```

## Agent 绘图调度

服务端只根据用户本轮请求开放必要工具，避免普通文档问答误触发高成本绘图：

- 数据探索：优先 Seaborn/Plotly；适合查看分布、异常值和交互关系。
- 论文正式图与验证图：优先 Matplotlib/Seaborn，通过 Code Interpreter 执行并回传 PNG、SVG 或 PDF。
- 流程、网络与模型结构：优先 Graphviz/NetworkX；适合直接嵌入论文的小图可由 Agent 返回 TikZ/PGFPlots。
- 封面、插画与非定量概念视觉：仅在请求明确匹配时开放 `image_generation`。该能力不得生成统计证据、精确数据或替代真实实验结果。

可通过 `.env` 中的 `OPENAI_CODE_INTERPRETER` 和 `OPENAI_IMAGE_GENERATION` 分别关闭两类云端能力；`OPENAI_MAX_ARTIFACTS` 与 `OPENAI_MAX_ARTIFACT_BYTES` 控制单次回复回传产物的数量和大小。

## 内部团队登录

在 `.env` 中设置 `TEAM_NAME` 和 `TEAM_ACCESS_CODE`。团队成员只需输入自己的名称和共享口令；客户端会生成本机随机身份并保存 30 天会话，团队口令不会写入浏览器存储。服务端会限制连续错误口令尝试。开发环境未设置口令时允许直接输入名称进入，生产环境未设置口令时团队登录会自动关闭。

团队登录和 QQ/微信 OAuth 属于两个独立登录域：分别使用 `tg_team_session` / `tg_oauth_session` HttpOnly Cookie 和独立的客户端 token 存储。JWT 会记录登录域，服务端拒绝把团队 token 用到 OAuth 域（反向亦然）；退出一种登录方式不会清理另一种方式的会话。

在局域网内提供给其他成员时，把 `CLIENT_URLS` 设置为允许访问的前端地址列表（逗号分隔，第一个地址用于生成邀请链接），并将 `PUBLIC_API_URL`、`PUBLIC_COLLAB_URL` 设置为成员设备可访问的服务端地址，不能继续使用成员各自机器上的 `localhost`。生产环境应使用 HTTPS/WSS，并更换强随机 `SESSION_SECRET` 与团队口令。

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
