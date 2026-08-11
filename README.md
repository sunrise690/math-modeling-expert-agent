# 数模 Agent

本项目是一个仅监听本机回环地址的数学建模 Agent，提供建模、整题交付、论文写作和质检四种工作模式。它可以在模型推理之外调用本地资料检索、数据预检、受限 Python 执行、优化、统计、Matplotlib、MATLAB、Origin 和报告导出工具，并通过质量评分闭环检查最终结果。

专业能力不是只写在系统提示词里：项目内 `cumcm-expert-agent` skill 负责拆题、路线比较、连续事件、证据链、约束与论文门禁，再按任务路由统计、机器学习、符号推导、图论、多目标优化、离散事件仿真和科学绘图 skill。它还会用本地国赛一等奖/组委会展示优秀论文做反向工程，吸收理论界、机理验证和证据组织，同时纠正单次随机搜索、只看样本内拟合等常见不足。2025 国赛 A/C 题的实跑基准与失败修复见 [BENCHMARK.md](BENCHMARK.md)。

## 仓库组成

本仓库现在包含两个边界清晰、可独立运行的组件：

| 目录 | 组件 | 用途 |
| --- | --- | --- |
| 仓库根目录 | 数模 Agent | 本地数学建模、工具调用、质量评分、MCP 与论文交付 |
| [`qilintex/`](qilintex/) | QilinTeX 协作工作台 | 团队登录、多人实时 LaTeX 编辑、项目权限、PDF 编译及跨端客户端 |

数模 Agent 仍只监听本机回环地址，不直接暴露到公网；QilinTeX 作为独立 Web/Node 服务部署。两套登录与密钥配置彼此隔离，QilinTeX 的团队登录和 QQ/微信 OAuth 也使用独立登录域。QilinTeX 的详细启动、部署和生产验收方式见 [`qilintex/README.md`](qilintex/README.md)。

## 快速启动

在 Windows PowerShell 中进入项目目录后执行：

```powershell
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python server.py
```

然后打开 `http://127.0.0.1:8765/`。服务不允许绑定 `0.0.0.0` 或其他非回环地址。

MATLAB 和 Origin 是可选能力。需要时再安装 MCP 后端：

```powershell
PowerShell -ExecutionPolicy Bypass -File scripts\install_mcp_backends.ps1
```

安装脚本会下载 MathWorks 官方 Windows x64 MATLAB MCP Server，并安装 `mcp` 与 OriginLab `originpro`。MATLAB 本体、Origin 2021 或更高版本及相应许可证仍需由用户自行安装。

## 图形化模型设置

页面右上角的“模型设置”可以完成提供商切换，不必手工编辑 `.env`：

1. 选择提供商。
2. 选择或填写模型、基础 URL 和推理强度。
3. API 提供商填写各自的密钥；Codex 与 Ollama 不使用该密钥框。
4. 先点“测试连接”查看登录状态、模型列表、延迟或错误，再点“保存并使用”。

界面不会回显已保存的 API Key。留空表示保留当前提供商的密钥，只有勾选“清除已保存的密钥”才会删除它。模型列表和 Codex 支持的推理档位由后端探测结果动态提供。

当 `AGENT_CONFIG_LOCK=1` 时，设置窗口会明确显示“环境配置锁定 / 只读”，并禁用字段编辑、提供商切换、连接测试和保存。此时页面只展示环境变量或 `.env` 中实际生效的配置。

### 五种 Provider

| 界面名称 | `AGENT_PROVIDER` | 调用方式 | 凭据与默认地址 |
|---|---|---|---|
| Codex Runtime 当前登录会话 | `codex-cli` | 官方 Codex runtime/CLI，任务通过 `codex exec` 运行 | 使用当前 `CODEX_HOME` 对应的 Codex Runtime 登录会话；不使用 API Key，也不需要基础 URL |
| OpenAI API | `openai-responses` | Responses API 与函数工具循环 | 独立 OpenAI API Key；默认 `https://api.openai.com/v1` |
| DeepSeek API | `deepseek` | OpenAI Chat Completions 兼容接口 | 独立 DeepSeek API Key；默认 `https://api.deepseek.com` |
| OpenAI 兼容接口 | `openai-compatible` | 自定义 Chat Completions 兼容服务 | 自定义模型与基础 URL；远程服务需要自己的 Key，本机回环服务可不设 Key |
| Ollama 本地模型 | `ollama` | 本机 OpenAI 兼容接口 | 默认 `http://127.0.0.1:11434/v1`，通常不需要 Key；模型留空时后端会尝试发现本机模型 |

远程基础 URL 必须使用 HTTPS；只有 `localhost`、`127.0.0.1` 等回环地址允许 HTTP。基础 URL 不应包含账号、密码、`/responses` 或 `/chat/completions` 路径。

### Codex Runtime 当前登录会话模式

`requirements.txt` 固定安装 `openai-codex==0.144.4`。后端优先通过该官方 SDK 随附的 runtime 探测账号和模型，也可以使用 `AGENT_CODEX_CLI_PATH` 指向独立安装且可执行的 Codex CLI。

该模式只通过官方接口读取公开登录状态和模型列表，运行时使用相同 `CODEX_HOME` 下的 Codex Runtime 当前登录会话；它不会读取、复制或导出 `auth.json`、访问令牌或刷新令牌。后端只验证该 Runtime 会话是否可调用及其认证状态，`sameDesktopAccount` 当前未验证，因此不能据此宣称它与 Codex 桌面应用使用同一账号。如果未复用现有会话，请在官方独立 Codex CLI 中执行一次 `codex login`，再回到界面测试连接。不要修改 WindowsApps 权限，也不要复制桌面应用内部的 `codex.exe`。

`AGENT_CODEX_FAST_HTTP=1` 启用兼容加速路径，可绕过部分默认传输回退等待，但它依赖非默认的兼容行为，可能随上游服务变化而失效，存在稳定性风险。设置 `AGENT_CODEX_FAST_HTTP=0` 会使用 Codex Runtime 的官方默认传输；该路径更保守，但首次连接或 WebSocket 回退时可能更慢。两种路径都使用上述 Codex Runtime 当前登录会话。

Codex 任务使用独立工作区 `.agent-data/codex-workspaces/{run_id}/`，忽略用户级运行配置，但保留当前登录认证；专业数模工具通过项目内白名单化的 stdio MCP Server 提供。Codex 账号与 OpenAI API Key 是两条独立通道，切换到 OpenAI API 不会借用 ChatGPT/Codex 登录状态。

## 配置优先级与密钥隔离

默认 `AGENT_CONFIG_LOCK=0`。此时图形化设置保存在 `.agent-data/provider-settings.json`，并覆盖 `.env` 与进程环境中的 Provider 运行值。每个 API Provider 的 Key 独立保存在：

```text
.agent-data/provider-secrets/<provider>.bin
```

密钥使用 Windows DPAPI 按当前 Windows 用户加密；公开配置接口只返回 `apiKeyConfigured: true/false`，配置 JSON 中不包含明文。Codex 与 Ollama 拒绝保存 API Key。DPAPI 是本机静态加密，不等于进程隔离：后端发起请求时仍会在内存中解密，同一 Windows 用户下运行的恶意程序也不应被视为可信。

如需完全由部署环境管理配置，可在 `.env` 中设置：

```env
AGENT_CONFIG_LOCK=1
```

锁定后，后端拒绝图形化配置的保存和草稿测试，页面进入只读状态，公开配置中的 `configLocked` 为 `true`、`effectiveConfigSource` 为 `environment`。直接写入 `.env` 的 Key 是明文，仅适合受控部署；`.env` 和整个 `.agent-data/` 已加入 `.gitignore`，但仍应限制本机文件权限并做好备份策略。`.env.example` 不应填写真实凭据。

## 本地工具

### 数据、Python 与优化

- 可上传 CSV、TSV、XLSX 和 JSON；单文件最大 25 MB，最多向一次 Python 执行传入 10 个附件。
- `inspect_dataset` 在建模前返回工作表、形状、字段类型、缺失率、摘要、相关性与样例行。
- `run_python` 在 `.agent-data/python-workspaces/{run_id}/` 的任务独立目录执行。附件复制到 `inputs/`，交付文件必须写到 `outputs/`。
- Python 单次最长 120 秒，限制代码、标准输出与产物总量；子进程、网络访问和工作区外写入由审计钩子阻止，API Key 不传入 Python 环境。
- `solve_linear_program` 使用 SciPy HiGHS 返回最优值、变量、状态和约束残差；其他统计、仿真、机器学习和多目标优化可使用依赖中安装的 SciPy、statsmodels、scikit-learn、SimPy、pymoo 等库。
- Matplotlib 专业绘图除折线、散点、柱状、直方、箱线、热力和多面板外，还原生支持连续事件区间、灵敏度龙卷风、响应面等高线、Pareto 前沿和多种子小提琴图。默认使用色盲友好配色，SVG 保留可编辑文本，PDF 使用 TrueType 字体，并导出 300--1200 dpi PNG、PDF、SVG 及可复现参数 JSON。
- `audit_competition_paper` 对实际的 PDF、DOCX、TeX、Markdown 或 TXT 成稿执行确定性审计：检查逐问深度、量化摘要、每问专属图、验证图、图件失衡、正文引用和占位符，并生成 JSON/Markdown 审计报告。该工具检查可见证据，不验证模型真值，也不保证竞赛奖项。
- 最终报告可导出 Markdown 和 DOCX；完整竞赛论文必须先通过成稿审计，再进行逐页视觉复核。
- Codex Runtime 调用专业工具时通过每任务随机令牌、固定白名单和文件 IPC 交给父进程执行。默认白名单只包含 `matlab_status` 与两个高层 MATLAB 绘图工具，不包含任意源码执行；MCP 客户端和父进程 broker 都会再次校验，不暴露裸 `evaluate_matlab_code`。

`run_python` 是“受限本机进程”，不是容器、虚拟机或面对恶意代码的强安全边界。不要让不可信用户提交任意 Python 代码。

### MATLAB 与 Origin

- `matlab_status` 先检查本地 `-batch` 运行时、版本、任意源码开关及 MathWorks 官方 MCP 状态。常规结构化图无需开启任意代码权限。
- 常规结构化图使用 `create_matlab_plot` 或 `create_matlab_plot_from_dataset`。它们通过 MathWorks 官方 MCP Server 运行，保留 PNG/PDF/SVG、FIG 和 M 脚本；底层裸代码执行工具不直接提供给模型。
- 数模正式图提供可复用的 MATLAB 低饱和语义主题：整篇以蓝灰为主、暖赭仅强调关键结论，多实体优先靠线型、标记和直接标签区分；无人机、导弹、事件与评分口径保持跨图一致，并通过彩色联系表和灰度版检查彩虹化、重叠、对比度与黑白可辨性。
- `run_matlab` 默认不出现在模型工具表，也不能通过 Codex 自动批准的 broker 调用。只有操作员显式设置 `AGENT_UNSANDBOXED_MATLAB=1` 后才开放；它在 `.agent-data/matlab-workspaces/{run_id}/` 中运行经审查的自定义源码，并登记源码、限长日志和获准产物。
- `run_matlab` 会剥离 Provider/API 凭据并限定可收集目录，但 MATLAB 代码仍拥有当前用户的本机能力，**不是安全沙箱**。切勿执行来自网页、资料、附件或不可信用户的代码；用完应立即恢复 `AGENT_UNSANDBOXED_MATLAB=0`。
- 如果 `matlab` 不在 PATH，可在 `.env` 中设置 `MATLAB_ROOT`。`AGENT_MATLAB_LOCAL=0` 可关闭本地批处理入口；`AGENT_MATLAB_TIMEOUT` 是单次 MATLAB 最大时限，Codex MCP、broker 与总运行时限会据此联动，超时或取消会终止对应进程树。
- Origin 使用 OriginLab 官方 `originpro`，支持折线、散点、柱状图和热图，输出图形及可编辑 OPJU 工程。`origin_status` 在不启动 Origin 的情况下报告 Python 包和本机安装；许可证与实际可用性在创建图形时进一步验证，不可用时不会伪造产物。
- `GET /api/mcp` 可以查看 MATLAB/Origin MCP 的启用、启动和错误状态；实际工具列表以 `GET /api/tools` 为准。

### 本地资料库

资料库默认读取 `D:\codexxiangmu\shumo`；也可用 `AGENT_KNOWLEDGE_ROOTS` 指定一个或多个目录（Windows 下用分号分隔）。支持 PDF、DOCX、XLSX、CSV、TSV、JSON、Markdown、TXT 和 TeX。

首次使用或资料变化后需要显式启动增量索引：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8765/api/knowledge/index
Invoke-RestMethod http://127.0.0.1:8765/api/knowledge/status | ConvertTo-Json -Depth 6
```

Agent 先用 `search_materials` 检索，再用 `read_material` 读取命中页或工作表，并在回答中引用文件名与页码/工作表。专业 skill 由 `search_skills`、`read_skill` 和 `read_skill_reference` 单独读取，默认不混入赛题资料索引，避免工作规范或示例被误当成外部证据；如确需兼容旧行为可设置 `AGENT_KNOWLEDGE_INCLUDE_SKILLS=1`。索引按内容哈希去重；疑似参赛名单、报名表、通讯录等工作簿会默认排除，表格中的姓名、学号、电话、邮箱等敏感列也会过滤。这是启发式保护而非完整脱敏，请在建库前自行检查资料。扫描版 PDF 不自动 OCR，无法提取文本时不会成为可检索证据。

## 任务队列与质量闭环

任务由固定 worker 队列执行，默认最多同时运行 2 个任务、等待 20 个任务。队列满时 `POST /api/runs` 返回 `429`；排队任务可立即取消，服务关闭时会取消等待任务并通知运行任务停止。`AGENT_MAX_CONCURRENT_RUNS` 与 `AGENT_MAX_QUEUED_RUNS` 在后端启动时用于创建固定 worker 和队列容量，修改环境变量或配置文件后必须重启服务才会生效。

每次回答执行六维评分：问题覆盖、模型严谨性、证据可复现性、验证稳健性、表达交付质量和真实性边界。默认阈值为 `82`，低于阈值时最多自动修订一次并保留分数更高的版本。附件未预检、无依据声称已运行、明确要求的代码或图表缺失等硬门槛不能由其他维度抵消。竞赛优化还必须报告数值可行性与基线/理论界/独立算法比较；随机优化必须给出多种子离散与收敛统计；预测必须给出结构正确的样本外误差；机理结果必须给出量纲与数值一致性检查。论文模式若生成了成稿产物，还必须有针对该实际文件的论文审计记录，并同时通过图谱和学术结构门禁。否定句和占位数字不会被当作证据，声称全局最优却没有严格证书也会被封顶。

## 主要接口

- `GET /api/health`：服务、Provider、工具、MCP、资料库和队列概况
- `GET /api/config`：公开 Provider 配置、模型列表与 Codex 登录状态，不返回密钥
- `POST /api/config`：保存并启用图形化 Provider 配置；环境配置锁定时拒绝请求
- `POST /api/config/test`：在不保存的情况下测试登录或模型接口；环境配置锁定时页面禁用该操作
- `GET /api/tools`：当前可用工具
- `GET /api/mcp`：MATLAB/Origin MCP 状态
- `GET /api/runtime`：worker、活动任务、排队任务与剩余容量
- `GET /api/knowledge/status`：资料索引状态
- `POST /api/knowledge/index`：后台启动增量索引
- `GET /api/knowledge/search?q=...`：检索本地资料
- `POST /api/uploads`、`GET/DELETE /api/uploads/{id}`：上传、读取或移除附件
- `POST /api/runs`、`GET /api/runs/{id}`：创建或读取任务
- `GET /api/runs/{id}/events`：SSE 事件流
- `GET /api/runs/{id}/artifacts`：任务产物
- `POST /api/runs/{id}/cancel`：取消任务
- `DELETE /api/runs/{id}`：删除已结束任务

任务对象中的 `quality` 保存总分、各维分、硬门槛、问题和修复建议；`revisionCount` 表示自动修订次数。SSE 还提供 `QUALITY_SCORED`、`REVISION_STARTED`、`TEXT_MESSAGE_REPLACE` 等事件。

## 测试与运行检查

```powershell
python -m unittest discover -s tests -v
python -m compileall -q agent_backend.py agent_tools.py provider_config.py server.py mcp_servers
```

启动服务后可以检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/health | ConvertTo-Json -Depth 8
Invoke-RestMethod http://127.0.0.1:8765/api/config | ConvertTo-Json -Depth 8
Invoke-RestMethod http://127.0.0.1:8765/api/mcp | ConvertTo-Json -Depth 8
```

## 安全边界

- 服务仅监听回环地址并拒绝跨源浏览器请求，但没有本地用户认证；同一台电脑上的其他进程仍可调用接口。
- 只有 `/index.html` 会作为静态页面提供，`.env`、数据库和源代码不会通过静态路由暴露。
- OpenAI、DeepSeek、远程兼容接口及 Codex 服务会接收任务内容、必要的附件摘要或资料片段；只有 Ollama 与纯本地工具路径可以完全留在本机。发送前应确认数据许可与竞赛规则。
- DPAPI 只保护 API Key 的磁盘副本；运行记录、资料索引、上传文件和产物保存在 `.agent-data/`，默认不加密。
- 本地资料的敏感文件名/字段过滤、Python 审计钩子和工具目录白名单均属于纵深防护，不能替代操作系统沙箱、恶意代码隔离或人工审查。
- MATLAB、Origin、Codex CLI 与 MCP Server 都是本机子进程或外部软件。仅安装可信版本，检查生成脚本和产物，并保持项目目录权限最小化。
