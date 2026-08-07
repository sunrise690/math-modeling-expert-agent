# Claim–Evidence Map

本表仅用于内部证据审计，不进入论文正文。主口径为目标中心视线，完整圆柱为保守二次审计。

| Claim ID | 可进入论文的主张 | 子问题 | 证据产物 | 核验 | 状态 |
|---|---|---|---|---|---|
| C-Q1-INTERVAL | 给定策略的中心视线有效遮蔽为 1.435082102 s | Q1 | `validation/q1_q2_independent.json`; `figures/q1_occlusion_intervals.*` | 独立 `q1_independent.json` 几何实现交叉核验；Brent 边界残差 | PASS |
| C-Q2-OPTIMIZED | 中心视线主口径找到 4.832501802 s 的经核验策略 | Q2 | `validation/q1_q2_independent.json` | 固定种子全局搜索 + 连续边界精修；约束违反为 0 | PASS_WITH_LIMITATIONS |
| C-Q3-COVERAGE | 3 枚烟幕弹的中心视线并集为 6.415210811 s | Q3 | `outputs/result1.xlsx`; `validation/q3_q5_independent.json` | XLSX 哈希 + 回读重算 + 连续时间并集 | PASS_WITH_LIMITATIONS |
| C-Q4-COVERAGE | 3 架无人机方案的中心视线并集为 15.736598188 s | Q4 | `outputs/result2.xlsx`; `validation/q3_q5_independent.json` | XLSX 哈希 + 回读重算 + 约束审计 | PASS_WITH_LIMITATIONS |
| C-Q5-FEASIBLE | 五机十五弹高质量可行解的三导弹总并集为 53.083939170 s | Q5 | `outputs/result3.xlsx`; `validation/q3_q5_independent.json`; `figures/q5_coverage_gantt.*` | 固定种子受限路线库/beam；XLSX 回读；约束违反为 0 | PASS_WITH_LIMITATIONS |
| C-CRITERION-SENSITIVITY | 同一策略在完整圆柱口径下 Q3/Q4/Q5 为 6.332880278/10.435489069/41.355064194 s | Q3–Q5 | `validation/q3_q5_independent.json`; `figures/criterion_sensitivity.*` | 连续完整圆柱边界精修；审计值不高于主口径 | PASS |
| C-WORKBOOK-ROUNDTRIP | 三份提交工作簿可无损回读到数值策略 | Q3–Q5 | `outputs/result*.xlsx`; `validation/q3_q5_independent.json#workbook_roundtrip_validation` | 当前文件哈希与回读时哈希一致；坐标/时长/目标误差 < 1e-8 | PASS |
| C-Q5-NO-GLOBAL | Q5 只主张高质量可行性，不主张全局最优 | Q5 | `validation/q3_q5_independent.json#results.Q5.diagnostics` | 明确 optimality disclaimer | PASS |

## 使用规则

- 论文数值只从上述产物生成，不从聊天记录或手工抄录进入正文。
- 完整圆柱数值必须称为“对同一策略的保守二次审计”，不能与主优化口径混写。
- Q2 零引信延迟是闭可行域的边界结果；工程表达应同时给出 0.02 s 正延迟替代。
- Q3–Q5 均不得写“全局最优”，Q5 尤其应写“固定种子受限路线库得到的高质量可行解”。
