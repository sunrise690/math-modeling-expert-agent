# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

主要用户是共同参加数学建模竞赛的学生团队。他们需要在有限时间内完成赛题拆解、模型路线选择、代码与数据验证、图表证据整理、LaTeX 论文写作和协作交付。

> 当前用户范围由仓库能力与“为数模 Skill 做前端和 UI”的请求推断；结构化确认工具在本次会话不可用，后续可由用户修订。

## Product Purpose

数模工作台将数学建模 Agent 的阶段化工作流与 QilinTeX 多人论文写作放在同一前端、同一项目上下文中。成功不是“文件很多”，而是团队能随时知道当前阶段、阻塞风险、证据是否闭环以及下一步应执行什么。

## Positioning

产品把 `problem -> model -> computation -> evidence -> conclusion` 的证据链直接连接到协作论文界面；相邻的在线 LaTeX 编辑器通常只管理文档，而不会管理模型路线、工件合同和结论证据。

## Operating Context

- 团队围绕一个竞赛项目协作，角色可能覆盖建模、编程、写作与审查。
- 现有客户端支持项目、好友、实时协作编辑、AI 文档助手、LaTeX 编译与 PDF 预览。
- 数模总控 Skill 支持 `init`、`analyze`、`route`、`solve`、`visualize`、`write`、`audit`、`polish`、`status` 和 `end-to-end`。
- 首版前端聚焦流程驾驶舱，并保留进入论文编辑器的直接路径。

## Capabilities and Constraints

- 复用 React 19、Vite、TypeScript、Lucide、Yjs 与现有 API 结构。
- 不虚构比赛成绩、模型指标、用户、截止时间或已生成工件。
- 尚未提供工作流状态后端；首版必须诚实呈现“待生成/未连接”，并提供可复制的 Skill 命令入口。
- Web 客户端同时被 Electron 与 Capacitor 包装，响应式结构必须兼容桌面和窄屏。
- 现有登录、项目、好友、协作编辑、编译和 AI 助手行为必须保留。

## Brand Commitments

- 产品名统一为“数模工作台”；“数模 Agent”和“QilinTeX”是同一项目中的两个工作区，不是两个产品入口。
- 保留中文任务界面与清晰直接的操作文案；视觉与信息架构参考 VS Code Dark Modern，但不复制 VS Code 品牌资产。
- 活动栏、资源管理器、快速命令、工作区页签、分栏面板与状态栏应构成连续的桌面工具体验。
- 工作台应优先呈现一个当前任务、下一步命令和证据轨迹；QilinTeX 保持稳定的编辑器/PDF 分栏与编译入口。
- 标准操作使用标准文案，不用科幻化或游戏化术语替代。

## Evidence on Hand

- `README.md`：当前产品能力与技术边界。
- `apps/client/src/components/Workbench.tsx`：现有工作台结构与行为。
- `apps/client/src/styles.css`：当前 VS Code 深色主题、响应式布局与组件状态。
- 项目内置的 `skills/cumcm-expert-agent/` 及用户可选安装的数模 Skills：数模工作流、命令和工件合同。
- 当前没有真实赛题、模型结果、证据数量或比赛截止时间；界面不得把演示内容伪装成真实项目数据。

## Product Principles

1. 当前任务与下一步始终比总览统计更醒目。
2. 每个结论都能沿证据链返回模型与工件。
3. 复杂工作流通过阶段和渐进披露呈现，不通过堆叠卡片呈现。
4. 协作写作与建模流程是同一项目的两个视图，不是两套产品。
5. 缺失、警告和阻塞必须诚实可见。

## Accessibility & Inclusion

- 键盘可达、可见焦点、语义化按钮与导航。
- 不以颜色作为唯一状态信号。
- 窄屏采用结构重排与横向阶段导航，而不是缩小字号。
- 尊重 `prefers-reduced-motion`。
