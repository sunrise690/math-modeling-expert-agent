# 数据处理说明

统一运行编号：`cumcm-2025a-20260808-r3`。

## 原始输入与完整性

原始输入只有官方 `A题.pdf` 与 `result1.xlsx`、`result2.xlsx`、`result3.xlsx`。题面常数由程序显式录入，工作簿仅作为规定输出模板；所有文件在求解前按 SHA-256 与 `references/sources.md` 核验。原始文件不做覆盖写入。

## 清洗与转换

- 题面是确定性机理问题，不含可删除的观测样本、缺失值或异常值；因此未做插补、去极值、平滑或标准化。
- 空间统一为 m，时间统一为 s，速度统一为 m/s，角度在内部统一为 rad、表格与图中显示为 degree。
- `result*.xlsx` 中的中文表头、行序和工作表结构保持官方模板不变；数值策略写入副本 `outputs/result*.xlsx`。
- 连续遮蔽时长不由 Excel 舍入值直接计算，而由 Python 内部双精度策略重新求根；写表后再从工作簿回读并重构坐标、区间、共享航路、投放间隔和目标值。
- 用于候选排序的时间网格不进入最终报告精度。终稿时长使用连续裕度括根与 Brent 精化；多弹目标使用区间并集，禁止逐弹时长直接相加。

## 缺失、异常与适用边界

官方题面没有风场、定位误差、引信误差或浓度衰减分布，因此不人为构造缺失值、异常值或随机噪声，也不报告虚假的置信区间。完整圆柱遮蔽作为几何口径敏感性审计，不被称为现实环境不确定性分析。

## 处理后产物

- `validation/q1_independent.json`：Q1 独立几何复算；
- `validation/q1_q2_independent.json`：Q1/Q2 主计算、约束与连续边界；
- `validation/q2_multiseed.json`：Q2 多种子收敛轨迹与终值离散；
- `validation/q3_q4_multiseed.json`：Q3/Q4 多种子局部精化轨迹与终值离散；
- `validation/q3_q5_independent.json`：Q3–Q5 策略、连续复算、完整圆柱审计和工作簿回读；
- `outputs/result1.xlsx`、`result2.xlsx`、`result3.xlsx`：可提交策略表；
- `figures/figure_manifest.json`：每幅图的数据源、单位、主张、解释与文件哈希；
- `paper/main.pdf`：由上述已核验产物生成的终稿。
