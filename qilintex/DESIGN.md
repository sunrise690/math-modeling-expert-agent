---
name: "Qilintex"
description: "安静、聚焦、任务优先的数学建模与协作论文工作台"
colors:
  canvas: "#0f0f0f"
  surface: "#171717"
  surface-subtle: "#1f1f1f"
  surface-hover: "#262626"
  ink: "#f4f4f5"
  ink-muted: "#a1a1aa"
  divider: "#2b2b2b"
  divider-strong: "#3f3f46"
  accent: "#f4f4f5"
  accent-hover: "#ffffff"
  accent-soft: "rgba(244,244,245,.08)"
  signal: "#22c55e"
  danger: "#ef4444"
  danger-soft: "rgba(239,68,68,.1)"
  code-surface: "#121212"
  pending-ink: "#725d19"
  pending-soft: "#f7efcf"
typography:
  display:
    fontFamily: "JetBrains Mono, IBM Plex Mono, Cascadia Mono, monospace"
    fontSize: "28px"
    fontWeight: 760
    lineHeight: 1.18
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "JetBrains Mono, IBM Plex Mono, Cascadia Mono, monospace"
    fontSize: "22px"
    fontWeight: 760
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  title:
    fontFamily: "JetBrains Mono, IBM Plex Mono, Cascadia Mono, monospace"
    fontSize: "14px"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: "normal"
  label:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "10px"
    fontWeight: 650
    lineHeight: 1.4
    letterSpacing: "0.04em"
  code:
    fontFamily: "Cascadia Code, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
rounded:
  paper: "5px"
  tool: "7px"
  control: "8px"
  field: "9px"
  stage: "10px"
  panel: "12px"
  pill: "999px"
spacing:
  2xs: "3px"
  xs: "6px"
  sm: "8px"
  md: "10px"
  lg: "12px"
  xl: "14px"
  2xl: "16px"
  3xl: "20px"
  4xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 11px"
    height: "34px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 11px"
    height: "34px"
  input-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "46px"
  navigation-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "38px"
  stage-active:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.tool}"
    padding: "7px 9px"
    height: "52px"
  card-task:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "24px"
  command-surface:
    backgroundColor: "{colors.code-surface}"
    textColor: "{colors.ink}"
    typography: "{typography.code}"
    padding: "14px 15px 14px 25px"
    height: "82px"
  status-pending:
    backgroundColor: "{colors.pending-soft}"
    textColor: "{colors.pending-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "5px 8px"
---

# Design System: Qilintex

## Overview

**Creative North Star: "The Modeling Thread / 建模线程"**

“建模线程”把一场数学建模竞赛组织成一条可监督的任务线程：用户从项目进入当前阶段，读取真实状态，执行一条明确命令，审查过程输出与证据，再进入论文视图。整体气质是 focused、quiet、task-first；信息密度服务于连续工作，而不是制造后台仪表盘的忙碌感。

视觉直接采用 Codex 深色主题的中性层级，并保留 Overleaf 式稳定的源文件/PDF 工作区。近黑画布承托三档深灰表面，白色用于主要文字与操作，绿色仅标记已完成、已同步等真实状态；层级来自表面色差和 1px 边界。缺失、等待、失败和未连接必须用文字与图形如实呈现。

**Key Characteristics:**

- 单一当前任务优先于总览统计。
- Codex 近黑画布、深灰表面与白色主操作构成长时工作环境。
- 1px 边界、方形控件和紧凑工具栏建立明确的工具感。
- 项目、任务线程、过程输出、审核结果与论文编辑器保持连续上下文。
- 状态表达诚实且不只依赖颜色。

## Colors

色彩采用 Codex 深色中性层级；白色承担主动作与当前定位，绿色只表示可信完成状态，红色与琥珀色分别保留给失败和待确认状态。

### Primary

- **主文字 / 主动作** (`accent`, #f4f4f5)：用于主要按钮、当前阶段、焦点轮廓与高优先级文字。
- **悬停白** (`accent-hover`, #ffffff)：仅用于主要动作悬停反馈。
- **白色弱面** (`accent-soft`, rgba(244,244,245,.08))：用于选中阶段和轻量聚焦背景。
- **状态绿** (`signal`, #22c55e)：仅用于完成、通过和已同步状态。

### Tertiary

- **错误红** (`danger`, #ef4444) 与 **错误暗底** (`danger-soft`, rgba(239,68,68,.1))：仅用于失败、诊断和阻塞反馈，并始终配合文字。
- **待确认棕** (`pending-ink`, #725d19) 与 **待确认浅底** (`pending-soft`, #f7efcf)：用于“尚未连接”等未被数据证实的状态。

### Neutral

- **主画布** (`canvas`, #0f0f0f)：应用与工作流页面的持续背景。
- **工作面** (`surface`, #171717)：任务、工具条、侧栏和编辑器承载面。
- **次级工作面** (`surface-subtle`, #1f1f1f)：面板标题条与次级控件。
- **悬停面** (`surface-hover`, #262626)：中性控件悬停时的短暂表面变化。
- **主文字** (`ink`, #f4f4f5)：标题、正文与主要图标。
- **静音灰** (`ink-muted`, #a1a1aa)：说明、元数据和等待状态；不得用于关键操作文案。
- **细分隔线** (`divider`, #2b2b2b)：默认 1px 面板、列表与工具栏分隔。
- **强分隔线** (`divider-strong`, #3f3f46)：输入边界和需要更强结构感的分隔。
- **代码面** (`code-surface`, #121212)：命令与运行输出的专用背景。

### Named Rules

**The Quiet Signal Rule.** 绿色只出现在可信完成状态；当前操作统一使用白色，不把状态色扩展成品牌色块。

**The Honest State Rule.** 成功、等待、失败和离线状态必须同时提供可读文案或图标，颜色永远不是唯一证据。

## Typography

**Display Font:** `JetBrains Mono`（回退至 `IBM Plex Mono`、`Cascadia Mono` 与 `monospace`）  
**Body Font:** 与 Display 相同的等宽字体栈  
**Label/Mono Font:** 与 Display 相同

**Character:** 系统字体确保中文、数字与英文命令在不同 Windows 和 Web 包装环境中稳定清晰。层级依靠字号、字重和留白建立，不依赖装饰字体；等宽体只标记可复制命令、工件路径和源代码。

### Hierarchy

- **Display**（760，28px，1.18）：当前任务标题与主要空状态标题；移动端降至 23px，避免压缩结构。
- **Headline**（760，22px，1.25）：项目或面板首标题；移动端可降至 18px。
- **Title**（650，14px，1.4）：卡片标题、证据面板和分区标题。
- **Body**（400，13px，1.65）：任务说明与关键解释，正文宽度通常限制在 70ch 内。
- **Label**（650，10px，0.04em）：工具按钮、状态与面板标签；只有“源文件/输出”等结构标签可使用大写化或扩字距。
- **Code**（400，11px，1.5）：命令与输出；长命令允许换行，文件路径优先单行省略。

### Named Rules

**The Working Type Rule.** 中文系统字体是默认表达，等宽字体只服务于可执行或可定位内容，不能把普通界面文案伪装成终端输出。

## Layout

桌面端采用两层稳定骨架：固定 216px 的项目侧栏与剩余工作区，顶部项目栏固定为 58px。工作流主体使用 `22px clamp(20px, 2.6vw, 38px) 26px` 的自适应内边距；阶段条横向排列，当前任务与交付物占主列，300px 证据检查器占辅列。主任务标题限制在约 30ch，说明限制在约 70ch，让“下一步”先被读到。

论文视图遵循稳定的 source/PDF 分栏。默认源文件占 52%，可通过可访问的分隔柄在 30%–75% 之间调整；编译、分享、AI 与视图切换固定在项目栏，不随正文滚动。流程与论文是同一项目的两个视图，切换时不丢失项目上下文。

在 1080px 以下，证据检查器移至任务下方，证据链变为横向滚动行；在 760px 以下，252px 侧栏变成抽屉，阶段项以固定约 112px 宽度横向滚动，内容按“任务→命令→门槛→交付物→证据”重排。编辑器与 PDF 改为纵向堆叠且各自至少 52vh；不得通过缩小正文字号来维持桌面列数。

## Elevation & Depth

系统完全扁平：画布、侧栏、工作面和工具面通过深灰色阶与 1px 边界分层。静止卡片、按钮、移动侧栏、模态和 PDF 占位均不使用投影。

### Shadow Vocabulary

- 无阴影；脱离文档流的层级使用遮罩、表面色与 1px 边界表达。

### Named Rules

**The Flat-by-Default Rule.** 如果 1px 边界和表面色差已经能说明层级，就不添加阴影。

## Shapes

形状是精确的工具型。控件、阶段容器、卡片、输入框与模态均使用直角；所有结构面以 1px 实线边界为主，分栏柄保持窄而可抓取，焦点使用 1px 白色外轮廓与 2px 偏移。

**The Square Surface Rule.** 不用圆角和胶囊制造层级，结构仅由色阶、边界与留白建立。

## Components

### Buttons

- **Shape:** 直角、常规高度 32px；重点动作可增至 34px。
- **Primary:** 白底、近黑字；只用于编译、创建和登录等当前主动作。
- **Hover / Focus:** 悬停提高到纯白；键盘焦点统一使用 1px 白色外轮廓。
- **Secondary / Ghost:** 次级按钮使用深灰底、强分隔线与静音文字，悬停时提高一级表面亮度。

### Chips

- **Style:** 状态使用直角边框和紧凑 `5px 7px` 内边距。
- **State:** “未连接”使用琥珀文字与暗底；当前阶段使用带编号的选中块。

### Cards / Containers

- **Corner Style:** 主要任务、交付物与证据面板均为直角。
- **Background:** `#171717` 工作面置于 `#0f0f0f` 画布之上；命令区使用 `#121212`。
- **Shadow Strategy:** 静止面板无阴影，依赖 1px 细分隔线。
- **Border:** 默认使用细分隔线；输入和次级操作可使用强分隔线。
- **Internal Padding:** 主任务头部约 24–25px，紧凑证据面板约 20px，移动端收紧至 16px。

### Inputs / Fields

- **Style:** 代码暗底、强分隔线、直角；单行输入高 44px，文本区维持 1.5 行高。
- **Focus:** 白色插入光标与 1px 外轮廓，不用发光阴影。
- **Error / Disabled:** 错误使用红字、浅红底与可读说明；禁用态使用中性灰并改变光标，不能只降低对比。

### Navigation

侧栏导航与项目列表采用 36px 左对齐直角行；默认文字为静音灰，悬停和选中提高一级表面亮度，并以左侧白色导轨标记当前项。项目栏里的“流程/论文”使用紧凑直角分段控件。窄屏侧栏作为可关闭抽屉，阶段导航保持横向滚动。

### Task Thread

任务线程是系统的签名组件：白色大号编号、左侧细导轨、单一大标题和短说明构成任务头；深黑命令区把下一步操作放在视觉中轴；“完成条件”紧随其后，形成“意图→执行→审核”的顺序。

### Source / PDF Workspace

源文件和 PDF 各有 34px 标签栏，并由 7px 可键盘调节的分隔柄连接。PDF 未生成、编译失败和成功预览分别使用明确内容状态；编译按钮和布局切换始终位于固定项目栏。

## Do's and Don'ts

### Do:

- Do 把当前任务、下一步命令和完成条件放在同一连续阅读路径中。
- Do 用 Codex 深色中性色阶、1px 边界与直角表面维持安静而精确的工具感。
- Do 让阶段、交付物、证据和编译结果使用真实文字状态，并为图标提供可访问标签。
- Do 在窄屏重排结构、横向滚动阶段条并纵向堆叠 source/PDF，而不是缩小正文字号。
- Do 尊重 `prefers-reduced-motion`，让状态变化在近乎无动画时仍然可理解。

### Don't:

- Don't 恢复旧 Swiss 蓝色网格、Aurora 渐变、装饰性 hero 或密集统计仪表盘。
- Don't 把状态绿铺成装饰背景，或让多个白色主按钮同时竞争注意力。
- Don't 给静止卡片和普通按钮添加投影、玻璃拟态、发光或厚重立体效果。
- Don't 用游戏化、科幻化术语替代“编译”“阶段”“通过标准”“待生成”等标准操作文案。
- Don't 把推测进度、虚构指标或尚未生成的工件呈现为已完成事实。
