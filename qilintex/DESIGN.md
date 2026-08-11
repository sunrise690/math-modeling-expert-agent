---
name: "数模工作台"
description: "参考 VS Code Dark Modern 的数学建模与协作论文工作台"
colors:
  titlebar: "#181818"
  activitybar: "#181818"
  sidebar: "#1f1f1f"
  editor: "#1e1e1e"
  panel: "#252526"
  hover: "#2a2d2e"
  border: "#2b2b2b"
  border-strong: "#464647"
  foreground: "#cccccc"
  muted: "#969696"
  focus: "#007fd4"
  action: "#0078d4"
  statusbar: "#007acc"
  selection: "#264f78"
  success: "#89d185"
  error: "#f14c4c"
typography:
  interface: "Segoe UI Variable Text, Segoe UI, system-ui, sans-serif"
  code: "JetBrains Mono, Cascadia Code, Consolas, monospace"
---

# Design System：数模工作台

## 视觉方向

界面采用 VS Code Dark Modern 的信息架构与深色层级，但不复制 VS Code 品牌图形。目标是让参赛团队在同一项目里连续完成“建模流程 → 计算证据 → QilinTeX 论文 → Agent 审查”，而不是在两个产品之间来回跳转。

主界面由活动栏、资源管理器、标题工具栏、工作区页签、主编辑区、可选 Agent 面板和状态栏构成。活动栏负责切换项目、好友和 Agent；“建模 Agent”与“QilinTeX”是同一项目中的两个编辑器页签。

## 色彩

- `#181818`：标题栏、活动栏和标签栏底色。
- `#1f1f1f` / `#1e1e1e`：资源管理器、编辑器和主要工作面。
- `#252526` / `#2a2d2e`：次级面板、悬停和选中面。
- `#2b2b2b` / `#464647`：面板与控件边界。
- `#cccccc` / `#969696`：主文字与次级文字。
- `#0078d4`：主要操作；`#007fd4`：键盘焦点；`#007acc`：底部状态栏。
- `#89d185` 与 `#f14c4c` 只表达成功和错误，并始终配合文字或图标。

不得使用渐变、玻璃拟态、装饰性发光或大面积品牌蓝。蓝色只用于当前操作、焦点、活动页签导轨和状态栏。

## 字体

普通界面使用 `Segoe UI Variable Text`、`Segoe UI` 和系统无衬线回退。LaTeX、命令、工件路径、日志与 CodeMirror 编辑器使用 `JetBrains Mono`、`Cascadia Code`、`Consolas` 和等宽回退。

界面文案必须是实际项目、动作或状态，不使用虚构指标、演示身份、装饰性英文副标题或科幻化命名。

## 结构

### 活动栏与资源管理器

桌面端活动栏固定为 48px，资源管理器为 232px。当前活动使用左侧 2px 蓝色导轨；项目树使用真实项目名称。窄屏隐藏活动栏并把资源管理器变成可关闭抽屉。

### 快速命令

标题栏中央提供可点击的快速命令入口，`Ctrl+P` 打开命令面板。命令只包含当前确实可执行的动作，例如新建项目、切换建模页签、打开 QilinTeX、打开 Agent、分享和编译；搜索为空时不伪造结果。

### 工作区页签

“建模 Agent”和“QilinTeX · main.tex”使用编辑器页签表达。活动页签与编辑区同色，并在顶部显示 1px 蓝色导轨。切换页签不改变项目身份，也不创建第二套登录或配置。

### 编辑器与 Agent

QilinTeX 保持源文件/PDF 可调分栏；Agent 作为右侧面板读取当前项目和当前页签上下文。建模阶段中的“交给 Agent”直接打开该面板并带入真实命令。

### 状态栏

底部 22px 状态栏展示同步状态、当前项目、工作区类型、编码和一体化后端标识。状态信息必须来自当前界面状态，不展示推测进度。

## 控件与可访问性

- 普通面板、页签和工具按钮保持方形或 0–3px 小圆角；快速命令入口和浮层可使用 VS Code 式 3–6px 圆角与阴影。
- 所有图标使用 Lucide，不以 Unicode 字符代替图标。
- 键盘焦点使用 `#007fd4` 1px 外轮廓；快速命令支持 `Ctrl+P`、回车执行和 `Escape` 关闭。
- 同步、成功、失败和离线状态同时提供文字或图标，不能只依赖颜色。
- 760px 以下重排编辑器/PDF 和隐藏非必要状态项，不通过缩小正文字号维持桌面布局。
- 尊重 `prefers-reduced-motion`。

## 产品边界

数模 Agent 与 QilinTeX 可以由不同后端进程提供能力，但对用户始终表现为一个前端、一个项目和一个工作台。任何新入口都必须继续复用同一项目、登录、成员与数据目录约定。
