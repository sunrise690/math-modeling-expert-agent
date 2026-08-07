# 主张与证据映射

| ID | 主张 | 证据 | 代码 |
|---|---|---|---|
| C1 | 孕周对 log(Y 浓度)有显著正效应 | `tables/q1_mixed_effects.csv` 中 `week_c=0.038239, p<1e-47`；F1 | `solve_q1` |
| C2 | BMI 对 log(Y 浓度)有显著负效应 | `bmi_c=-0.022398, p=0.002585`；F1 | `solve_q1` |
| C3 | 个体差异不可忽略 | `tables/q1_model_performance.csv`：ICC=0.7318，条件 R²=0.7705 | `solve_q1` |
| C4 | 问题 2 四组时点为 13w+3、14w+4、16w+2、19w+5 | `tables/q2_groups.csv`；F2 | `solve_q2_q3` |
| C5 | 问题 3 四组时点为 13w+6、15w+2、16w+3、19w+5 | `tables/q3_groups.csv`；F2 | `solve_q2_q3` |
| C6 | 多因素 AFT 未优于 BMI 主模型 | `tables/q2_q3_model_comparison.csv`：多因素 AIC 更高 | `solve_q2_q3` |
| C7 | 阈值误差可让推荐时点变化最多 17 天 | `tables/q2_q3_error_sensitivity.csv`；F3 | `solve_q2_q3` |
| C8 | 女胎逻辑回归 AUC=0.826，优于传统 Z 规则 0.479 | `tables/q4_model_metrics.csv`；F4 | `solve_q4` |
| C9 | 女胎主模型阈值 0.5 时召回率 0.746、特异度 0.768 | `tables/q4_model_metrics.csv`、`q4_confusion_matrix.csv`；F5 | `solve_q4` |
| C10 | 嵌套孕妇分组校准将 Brier 分数由 0.158 降至 0.081，ECE 为 0.035 | `tables/q4_calibration_summary.csv`、`q4_calibration_bins.csv`；F4C | `solve_q4` |
