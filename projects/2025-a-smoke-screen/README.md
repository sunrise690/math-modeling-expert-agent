# 2025 国赛 A 题：烟幕干扰弹的投放策略

这是数模 Agent 的连续几何与组合优化盲测项目。题面、官方模板和计算结果分离：原始 PDF/XLSX 只保存在本机 `source/` 并由版本库排除，代码、哈希清单、派生结果、图件、论文和验证报告可提交与复核。

## 一键核验与复现

在本项目目录运行：

```powershell
# 数秒内核验 JSON、XLSX、图件、哈希和数值不变量
python -B src/run_all.py --quick

# 核验现有正式结果，并用标准库 unittest 运行全部测试
python -B src/run_all.py

# 完整重跑 Q1--Q5 搜索、工作簿、圆柱审计和图件（耗时较长）
python -B src/run_all.py --recompute
```

`--quick` 与 `--recompute` 互斥，防止用缩小搜索覆盖正式结果。最终运行按多种子审计结果使用 Q3=`20250810`、Q4=`20250809`、Q5=`20250808`；Q2 使用 `20250808`--`20250815` 做独立重复。

14 组正式图全部由 `src/matlab/render_*.m` 生成；Python 只负责调用 MATLAB、检查产物并写入哈希清单，不参与正式绘图。默认流程校验版本库中已经生成并通过视觉复核的 42 个 MATLAB 产物；需要强制重绘时先设置 `CUMCM_FORCE_MATLAB_FIGURES=1`。重绘需要 MATLAB `-batch`；若 `matlab` 不在 PATH，请设置 `MATLAB_ROOT`。MATLAB 不可用或图形客户端异常时不会用 Python 静默改画。

`src/origin/render_q5_multivariate.py` 提供受审计的 OriginPro 高维辅助分析；运行 `python -B src/origin/render_q5_multivariate.py`，即可从同一验证 JSON 确定性生成九维规范矩阵、PCA 得分与相关载荷，并在 `support/multivariate/` 保存原始/标准化 CSV、旋转不变的圆周变量组尺度、发散色板、可编辑 OPJU、PNG/PDF/SVG、能力快照、退出证据和逐文件 SHA-256。渲染器会在同一隐藏会话中重开刚保存的 OPJU，核对 3 个图层、矩阵/得分/载荷工作表及数值；默认 `run_all.py` 再独立重算数据、核验 PDF 轮廓字体结构、SVG 标签碰撞和精确闭包。在本机 Origin 可执行文件存在时还会重算其哈希；离线/GitHub 验证则使用已记录能力快照。`--recompute` 会在 MATLAB 正式图之前强制重跑该 Origin 脚本，能力或导出失败即中止，不静默换后端。该辅助产物不替换论文中已验证的 MATLAB 正式图。

## 判据与结论边界

- 主评分使用导弹到真目标几何中心的有限视线，Q2--Q5 的优化和模板填报均按此口径。
- 对同一策略另做完整圆柱全遮蔽的连续保守审计；它是性能下界，不替代主评分。
- Q5 是固定种子、受限路线库与波束搜索得到的经连续复算可行解，所有硬约束违反量为 0；尚无多种子离散证据和全局最优证书，因此不使用“稳定”或“高质量”措辞。
- Q2 的零引信延迟是闭可行域边界结果，另提供 `0.02 s` 正延迟工程方案。

## 主要产物

- `src/`：三维运动学、连续事件求根、Q1--Q5 求解、工作簿回读和专业绘图。
- `outputs/result1.xlsx`、`result2.xlsx`、`result3.xlsx`：按官方模板生成的提交结果。
- `validation/`：独立几何复算、求根残差、约束和工作簿回读证据。
- `figures/`：14 组 MATLAB 生成的 PNG/PDF/SVG 正式图及 claim 绑定清单；全部绘图源码位于 `src/matlab/`。
- `reports/summary.json`、`verification_report.md`、`redteam_review.md`：结构化结果与边界审计。
- `references/claim_evidence_map.md`：论文主张到可重生成证据的映射。
- `paper/main.tex`、`paper/main.pdf`：正式中文论文及可编译源文件。
- `support/`：自审、Origin 可编辑辅助证据和 AI 使用记录，不进入论文正文。
