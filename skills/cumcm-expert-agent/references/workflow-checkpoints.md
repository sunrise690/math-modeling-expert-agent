# 可恢复阶段与门禁

## 目录

1. 适用范围
2. 阶段与门禁
3. 使用方式
4. 证据与确认规则
5. 回退和恢复

## 1. 适用范围

整题工程、完整论文和跨回合续做任务使用本状态协议。快速咨询、单段润色和一次性单问解释不强制初始化状态文件，但仍遵守主 Skill 的真实性与验证门禁。

状态文件写入 `<PROJECT_ROOT>/.modeling-agent/workflow-state.json`。它只记录流程、门禁证据哈希和用户确认，不代替模型、计算结果或论文证据。

## 2. 阶段与门禁

阶段只能相邻推进，不得跳过：

| 当前阶段 | 下一阶段 | 必须通过的门禁 |
|---|---|---|
| `intake` | `parse` | `input_audit`：题目、附件、模板和规则已盘点 |
| `parse` | `model` | `problem_contract`：逐问目标、变量、单位、约束和输出已定义 |
| `model` | `prototype` | `model_contract`：基线、主模型、升级条件和验证计划已冻结，并取得用户确认 |
| `prototype` | `solve` | `prototype_run`：最小真实链路成功运行且有独立核对 |
| `solve` | `validate` | `full_solution`：全部子问已有真实结果和约束复核 |
| `validate` | `evidence` | `validation`：问题匹配的独立复算、灵敏度或鲁棒性通过 |
| `evidence` | `write` | `claim_evidence`：关键主张已绑定公式、表、图、代码和来源 |
| `write` | `package` | `paper_audit`：正文、摘要、图表、引用和附录一致性通过 |
| `package` | `complete` | `package_rebuild`：从干净交付目录完成重建和最终检查 |

门禁只有 `PASS` 才能推进；`FAIL` 和 `BLOCKED` 记录证据但保留当前阶段。不得用 `LIMITED`、口头说明或改写措辞代替通过。

## 3. 使用方式

初始化：

```powershell
python "<SKILL_ROOT>/scripts/workflow_state.py" init `
  --project-root "<PROJECT_ROOT>" --competition CUMCM --year 2026 --problem-id A
```

查询状态：

```powershell
python "<SKILL_ROOT>/scripts/workflow_state.py" status --project-root "<PROJECT_ROOT>"
```

通过门禁并推进一个阶段：

```powershell
python "<SKILL_ROOT>/scripts/workflow_state.py" advance `
  --project-root "<PROJECT_ROOT>" --to parse `
  --gate input_audit --status PASS `
  --evidence "evidence/input-audit.json"
```

从 `model` 进入 `prototype` 时，额外传入用户本次真实确认的简短记录：

```powershell
python "<SKILL_ROOT>/scripts/workflow_state.py" advance `
  --project-root "<PROJECT_ROOT>" --to prototype `
  --gate model_contract --status PASS `
  --evidence "evidence/model-contract.json" `
  --user-approval "用户确认按 2026-08-12 提交的逐问模型方案进入编程"
```

## 4. 证据与确认规则

- 每个门禁至少绑定一个 `PROJECT_ROOT` 内的现有文件；脚本记录相对路径、大小和 SHA-256。
- 门禁证据优先使用机器可读审计报告、模型合同、运行日志、约束复核或重建报告，不用聊天摘要冒充。
- 用户确认只决定是否按已汇报的模型方案进入编程，不替代数学正确性审查。不得虚构确认、把沉默视为确认或用 Agent 自评代替确认。
- 用户在当前请求中明确要求“无需确认，直接完成”时，可把该原句作为预授权记录；授权范围变化后重新确认。
- 单个门禁通过不代表最终结论正确；最终仍需执行 `audit_modeling_workflow` 和论文/复现审计。

## 5. 回退和恢复

证据文件缺失、大小变化或哈希变化时，`status` 自动回退到受影响门禁之前，并使该门禁及全部下游门禁失效。修改模型合同、权威结果、验证或论文后必须先运行 `status`，不得沿用旧 PASS。

主动回退：

```powershell
python "<SKILL_ROOT>/scripts/workflow_state.py" rollback `
  --project-root "<PROJECT_ROOT>" --to model `
  --reason "验证发现边界条件口径错误，需要重建模型合同"
```

回退只修改状态，不删除用户产物。保留失败证据和旧结果用于审计，但不得继续把它们当作当前权威结果。
