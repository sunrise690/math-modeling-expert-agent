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
| 图/路径/网络流 | `run_python` + networkx | 图构造、可行性、目标值 | 路径逐边复核 |
| 离散事件/排队 | `run_python` + simpy | 预热、重复次数、置信区间 | 理论特例或加长仿真 |

## 附件与资料

1. 对每个相关附件调用 `inspect_dataset`，确认工作表、字段、类型、缺失和样例。
2. 本地资料先 `search_materials`，再对命中片段 `read_material`。
3. 引用时保留文件名、页码或工作表位置；不能仅凭标题推断。
4. 扫描 PDF 无文本时标记 OCR 缺口，不猜内容。

## 绘图引擎

- Matplotlib：默认数据分析与统计诊断静态图，保留 PNG + PDF/SVG。
- MATLAB：先调用 `matlab_status`。常规折线、散点、柱状或热图用 `create_matlab_plot`/`create_matlab_plot_from_dataset`。`run_matlab` 可执行当前用户权限下的本机任意代码且默认关闭；只有操作员显式设置 `AGENT_UNSANDBOXED_MATLAB=1`、状态确认已启用且源码可信时，才可用于工程机理、连续事件根、覆盖阶梯或三维轨迹。保留已执行 `.m`、日志、`.fig`、PNG/PDF/SVG，图中数值必须与结果表同源。
- Origin：用户要求可编辑 Origin 工程且本机能力检查通过时使用，保留 `.opju`。
- 不为同一主张无意义地重复三种绘图引擎。
- 用户明确指定 MATLAB 时，运行时不可用就报告缺口；只有用户未限定引擎时才允许回退 Python。
