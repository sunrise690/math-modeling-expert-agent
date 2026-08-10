# 工具路由

## 先判定数学对象

| 数学对象 | 主工具 | 必须报告 | 独立校验 |
|---|---|---|---|
| 连续/非线性优化 | `run_python` + SciPy | 目标值、边界、约束违反、终止状态 | 多初值、网格或另一算法 |
| 多目标优化 | `run_python` + pymoo | Pareto 集、可行率、代数、种子 | 标量化或不同种子 |
| 线性/整数规划 | `solve_linear_program` 或 `run_python` | solver status、最优性/界、约束余量 | 直接代回约束 |
| 机理/ODE/轨迹 | `run_python`；仅经操作员显式授权时用 `run_matlab` | 方程、初边值、步长、守恒/几何误差 | 解析特例、步长收敛 |
| 统计推断 | `run_python` + statsmodels | 假设、效应量、区间、诊断 | bootstrap 或稳健标准误 |
| 预测/分类 | `run_python` + scikit-learn | 划分策略、基线、指标、校准 | 分组/时序外推验证 |
| 高维联合选择/多变量结构 | `run_python` 建规范矩阵；能力检查后用 Origin 正式渲染 | 标准化参数、圆周变量组、样本量；若用 PCA 列解释方差与载荷 | 原尺度结果表、成对关系或留一/重采样稳定性 |
| 图/路径/网络流 | `run_python` + networkx | 图构造、可行性、目标值 | 路径逐边复核 |
| 离散事件/排队 | `run_python` + simpy | 预热、重复次数、置信区间 | 理论特例或加长仿真 |

## 附件与资料

1. 对每个相关附件调用 `inspect_dataset`，确认工作表、字段、类型、缺失和样例。
2. 本地资料先 `search_materials`，再对命中片段 `read_material`。
3. 引用时保留文件名、页码或工作表位置；不能仅凭标题推断。
4. 扫描 PDF 无文本时标记 OCR 缺口，不猜内容。

## 绘图引擎

按“证据对象 → 后端候选 → capability check → 固化 renderer”顺序路由，不以用户是否点名 Origin 作为唯一触发条件：

- **MATLAB**：连续事件函数与验根、几何构造、遮蔽/覆盖区间、调度阶梯、等比例轨迹和需要精确事件图层控制的时序图。先调用 `matlab_status`；标准结构化图用 `create_matlab_plot`/`create_matlab_plot_from_dataset`。`run_matlab` 可执行当前用户权限下的本机任意代码且默认关闭，只有操作员显式设置 `AGENT_UNSANDBOXED_MATLAB=1`、状态确认已启用且源码可信时才可使用。保留已执行 `.m`、日志、`.fig`、PNG/PDF/SVG、版本和哈希。
- **Origin**：规范数据表驱动的统计比较、标准化高维矩阵、分布/残差、PCA 辅证、响应面、等高线和数据驱动多面板图。可由 Agent 主动选择；先调用 `origin_status`，再确认许可证、自动化接口和当前版本能通过同一路径无交互导出 PNG/PDF/SVG。只验证“已安装”不算能力通过。正式产物必须保存已执行 Python/LabTalk、确定性派生 CSV/JSON、`.opju`、PNG/PDF/SVG、导出日志、版本清单和逐文件 SHA-256。
- **Matplotlib**：探索性分析、独立统计诊断和上述后端不适配的静态证据图，保留脚本与 PNG/PDF/SVG。它不是 MATLAB 或 Origin 失败后的隐式替身。

固化后端后禁止静默回退。若 capability check 或渲染失败，停止该图，报告具体缺口；只有在用户未限定后端且 `figure_intent.renderer_contract` 显式改写、来源闭包重建并重新通过图件审计后，才可换用另一引擎。不得沿用旧 `renderer`、旧 `.opju` 或旧哈希生成同名替代文件，也不为同一主张无意义地重复三种引擎。

高维数据先在 Python 中生成可审计的规范矩阵，再交给正式渲染后端。连续变量记录标准化参数；圆周变量以 `cos/sin` 成对并作为一个语义组，使用共享的旋转不变组尺度而不是逐列 z-score。PCA 仅作有逐项/累计解释方差和载荷支撑的辅助投影。只有 15 条联合选择数据时不得报告自然聚类；禁用雷达图、无证据任务的三维图和不可追踪的意大利面平行坐标。
