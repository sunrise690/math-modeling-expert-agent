# 2025 国赛 C 题：NIPT 的时点选择与胎儿异常判定

这是一个由 Agent 实跑完成的可复现建模项目，覆盖数据审计、四问建模、稳健性分析、正式图表和报告导出。

## 一键运行

```powershell
cd projects\2025-c-nipt
python src/run_all.py
```

原始题包和逐行 NIPT 数据不进入版本库。将官方附件放入 `data/raw/nipt_data.xlsx` 后运行；代码、聚合表、图形和论文可以复现并审计，但不得把这些结果用于医学诊断。

## 模型路线

| 子问题 | 主模型 | 关键控制 |
|---|---|---|
| 问题 1 | 随机截距混合效应模型 | 同一孕妇重复测量相关 |
| 问题 2 | 仅 BMI 的区间删失对数正态 AFT | 动态连续分组；90% 达标约束 |
| 问题 3 | 多因素区间删失 AFT | 只用检测前变量；阈值敏感性 |
| 问题 4 | 分组五折逻辑回归为主，RF/HGB/传统规则为基线 | 同一孕妇不跨折；关注 PR-AUC |

## 主要产物

- `paper/main.pdf`：28 页正式参赛稿，含完整推导、检验与参考文献
- `paper/main.tex`：正式参赛稿 LaTeX 源文件
- `paper/report.docx`：7 页简洁 Word 速读版
- `paper/report.pdf`：简洁 Word 版的逐页检查 PDF
- `paper/report.md`：模型结果摘要
- `src/run_all.py`：完整可复现代码
- `reports/summary.json`：结构化结果
- `tables/`：论文表格与结构化结果
- `figures/`：10 组期刊级正式图，均提供 600 dpi PNG、矢量 PDF 与可编辑 SVG
- `references/claim_evidence_map.md`：主张到证据映射
- `reports/redteam_review.md`：局限和红队审查
- `validation/latest_score.md`：正式稿严格质量评分（100/100）

## 结果边界

附件样本以高 BMI 人群为主，且存在大量左删失与有限的女胎阳性样本。模型结论仅用于竞赛数据分析，不构成医学诊断或临床建议。
