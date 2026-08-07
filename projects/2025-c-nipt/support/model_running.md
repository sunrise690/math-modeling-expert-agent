# 模型运行说明

在项目根目录运行：

```powershell
python src/run_all.py
```

脚本依次完成数据清洗、混合效应模型、区间删失 AFT、BMI 动态分组、阈值敏感性分析、女胎异常分类、图表和报告生成。固定随机种子写在 `src/run_all.py` 中。

主要输出：

- `reports/summary.json`：机器可读结果摘要
- `tables/`：模型系数、分组建议、性能指标和混淆矩阵
- `figures/`：PNG 与 PDF 双格式正式图
- `data/processed/`：可审计的中间数据
- `paper/report.md`：自动生成的中文建模报告

快速语法检查：

```powershell
python -m py_compile src/run_all.py
```
