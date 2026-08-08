# 运行日志

- 统一运行编号：`cumcm-2025a-20260808-r3`
- 日期：2026-08-08（Asia/Shanghai）
- Python：`python -B`

## 完整重算

执行：

```powershell
python -B projects/2025-a-smoke-screen/src/run_all.py --recompute
```

完整重算依次执行 Q1–Q5 求解、Q2 八种子验证、Q3/Q4 五种子验证、14 幅图重建、结果工作簿写入与回读、XeLaTeX 编译、论文成品审计和项目测试。总运行时间约 238 秒。

最终采用的分问种子：Q3 为 `20250810`，Q4 为 `20250809`，Q5 为 `20250808`。Q3、Q4 的最终报告值均与多种子原始运行中的最佳可行终值一致。

## PDF 复核

最终 PDF 为 23 页 A4。日志中 Overfull、缺字、未定义引用和构建错误均为 0；52 个字体全部嵌入。用 Poppler 按 120 dpi 渲染 `page-01.png` 至 `page-23.png`，并生成 4 张接触表；23 页均完成视觉检查。视觉记录绑定：

- PDF SHA-256：`c55cb78750490a4cbf0e61ac06d327a017f36caf20405b37428d1b001124c4e2`
- 输入联合 SHA-256：`1a7a707bc87ec338246831405fd91882d3c1fe73ce69113b7f8d1ecfeec59b40`

## 最终验证

执行：

```powershell
python -B projects/2025-a-smoke-screen/src/run_all.py
python -B -m unittest discover -s tests -v
python C:/Users/1/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/cumcm-expert-agent
git diff --check
```

结果：项目门禁 19/19 通过，项目测试 41/41 通过，Agent 根目录测试 93/93 通过，专家 Skill 校验通过，Git 差异检查通过。

任何论文输入、验证 JSON、图件、工作簿、TeX 或 PDF 发生变化后，都必须重新生成对应的编译、审计和视觉记录；旧记录不得跨哈希复用。
