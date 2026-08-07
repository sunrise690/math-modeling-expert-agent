# 竞赛论文自检报告

| 项目 | 状态 | 证据/待办 |
|---|---|---|
| 子问题覆盖 | PASS | `summary.json` 含 Q1–Q5；三个官方结果工作簿均已生成 |
| Claim–Evidence Map | PASS | `references/claim_evidence_map.md` 覆盖结果、敏感性、回读与最优性边界 |
| 数值与约束核验 | PASS | 15 项通过，0 项失败，0 项跳过 |
| 变量泄漏审计 | N/A | 机理—优化问题，无训练/测试标签或决策后变量；变量定义见 `references/variable_audit.md` |
| 数据一致性 | PASS | 官方源文件、输出 XLSX 与验证 JSON 由 SHA-256 绑定 |
| 模型口径 | PASS | 目标中心视线为主口径，完整圆柱为保守二次审计，未混用 |
| 稳健性/敏感性 | PASS_WITH_LIMITATIONS | 已检验重力、判据和完整圆柱；尚无 Q5 全局最优证书 |
| 图件 | PASS | 5 个图各有 PNG/PDF/SVG 和 claim ID；论文内图件已经人工逐页视觉复核 |
| 参考文献 | PASS | `main.tex` 有 8 个文献条目和 8 个对应引用键；日志无未定义引用 |
| PDF 技术 QA | PASS | `main.pdf` 为 12 页 A4，29 个字体全部嵌入，日志无布局/构建错误；见 `reports/pdf_qa.md` |
| PDF 视觉 QA（人工） | PASS | 已有人工逐页审查与当前 PDF SHA-256 绑定；不是由自动检查推断；见 `support/manual_pdf_qa.json` |
| 最优性措辞 | PASS | Q5 固定为“高质量可行解”，所有无全局证明的问题均禁止全局最优措辞 |

## 放行结论

数值、参考文献、PDF 技术检查和人工逐页视觉 QA 均已通过，当前终稿可放行。 如果后续重跑优化或重新编译 PDF，必须重新执行 `python -B src/run_all.py`；PDF 哈希变化会自动使旧人工视觉 QA 失效。
