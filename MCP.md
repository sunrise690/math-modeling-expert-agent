# MATLAB 与 Origin MCP

后端通过持久 stdio 会话连接 MCP Server。MCP Server 只在首次工具发现或调用时启动，后续任务复用同一会话；服务退出时关闭子进程。MCP 标准错误、结构化结果和文本结果会统一转换为 Agent 工具结果。

## MATLAB

- 上游：MathWorks 官方 `matlab/matlab-mcp-server`。
- 当前安装器下载 Windows x64 最新正式版，并关闭匿名遥测。
- 本机自动发现 PATH 中的 MATLAB，或读取 `.env` 的 `MATLAB_ROOT`。
- 原生工具：工具箱检测、代码检查、代码求值、脚本运行、测试运行。
- 高层工具：内联数据与上传数据绘图。
- 产物：300 DPI PNG、矢量 PDF/SVG、FIG、可复现 M 脚本。

MATLAB 代码求值被固定到当前任务的 `.agent-data/mcp-workspaces/{run_id}`；脚本检查和运行只接受当前任务工作区或产物目录中的 `.m` 文件。

## Origin

- 自动化接口：OriginLab 官方 `originpro`，通过 Origin Automation Server COM 启动本机 Origin。
- MCP 工具：`origin_status`、内部 `origin_create_plot`。
- Agent 高层工具：`create_origin_plot`、`create_origin_plot_from_dataset`。
- 图形：折线、散点、柱状、热力图。
- 产物：PNG/PDF/SVG 和可编辑 OPJU。

Origin MCP Server 可以正常启动并列出工具，但只有检测到 Origin 2021+ 本机安装及许可证环境时，绘图能力才标记为可用。

## 配置

```env
AGENT_MCP=1
AGENT_MATLAB_MCP=1
AGENT_ORIGIN_MCP=1
MATLAB_ROOT=D:\matlab
```

查看状态：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/mcp | ConvertTo-Json -Depth 8
```
