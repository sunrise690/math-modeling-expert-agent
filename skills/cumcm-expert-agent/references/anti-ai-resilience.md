# 可验证建模过程与反脆弱门禁

本规范用于抵御“AI 替代思考”导致的建模失真，不用于规避检测、伪装人工写作或删除真实的 AI 使用记录。目标是让任何最终结论都能沿“题面—假设—模型—计算—验证—修改”回溯。

## 六类风险与对应门禁

| 风险 | 必须留下的证据 | 失败门禁 |
|---|---|---|
| 用 Monte Carlo 或仿真替代机理 | 明确机理、仿真用途、校准/验证产物 | `mechanism_before_simulation` |
| 用 NP-hard 或复杂算法替代工程化简 | 降维、分解、近似或小规模精确策略及复验 | `np_hard_engineering_strategy` |
| 通用图表和空泛题注 | 图所支撑的主张、源数据证据、变量与单位 | `figure_semantics` |
| 编造来源、数据、因果或运行结果 | 可定位且已核验的来源、计算和验证证据 | `source_integrity`、`claim_evidence_consistency` |
| 假设、模型、结论之间逻辑断裂 | 稳定 ID 和完整的主张—证据—假设引用 | `assumption_traceability`、`claim_evidence_consistency` |
| 只生成一次答案，没有反馈迭代 | 触发问题、修改、复验结果、接受/回滚及运行证据 | `closed_loop_iteration` |

## 执行顺序

1. 先冻结题面事实、目标、变量、单位和约束，不把 Agent 推断写成题面事实。
2. 建立可执行简单基线，记录误差、不可行场景或计算瓶颈。
3. 只有基线证据证明不足时才提高 `complexityLevel`，并在 `upgradeEvidenceIds` 绑定证据。
4. 仿真只承担动态求解、稳健性或不确定性评估；必须先写 `mechanisms`。
5. 每个最终结果主张必须为 `verified`，引用已核验计算证据，并被一项通过的验证覆盖。
6. 记录至少一次真实闭环。无需为了凑次数反复换模型；一次有证据的修正优于多次无依据试参。
7. 完整解题或论文成稿提交前调用 `audit_modeling_workflow`。失败后修改模型、数据、代码或验证，再重新审计。

## Manifest 合同

顶层字段：

- `stage`：`draft` 或 `final`；只有 `final` 且全部门禁通过才算可交付。
- `problem`：`facts`、`objectives`、`variables`、`constraints`。每个变量含 `id`、`meaning`、`unit`。
- `assumptions`：每项含 `id`、`statement`、`basis`、`risk`、`validation`。
- `model`：机理、简单基线、主模型、复杂度、仿真/随机/NP-hard 策略。
- `evidence`：每项含稳定 `id`、`kind`、可回读 `locator`、布尔值 `verified`。
- `claims`：每项含 `id`、`kind`、`statement`、`status`、`final`、`evidenceIds`、`assumptionIds`。
- `validations`：每项含 `claimIds`、`type`、`metric`、`result`、`passed`、`evidenceIds`。
- `iterations`：每项含 `iteration`、`trigger`、`change`、`result`、`decision`、`evidenceIds`。
- `figures`：有图时，每项绑定 `claimIds`、`sourceEvidenceIds`、`captionClaim`；定量图必须给 `xUnit`、`yUnit`。
- `citations`：使用外部文献时，每项给出 `title`、`locator` 和 `verified`。

`model` 的关键字段：

```json
{
  "mechanisms": ["变量之间的守恒、因果或约束关系"],
  "baseline": {
    "name": "可执行简单基线",
    "rationale": "为什么它是合理起点",
    "evidenceIds": ["ev-baseline"]
  },
  "selected": {
    "name": "最终主模型",
    "rationale": "基线的哪项实际不足促成升级",
    "assumptionIds": ["a-1"]
  },
  "complexityLevel": "L1",
  "upgradeEvidenceIds": ["ev-baseline-gap"],
  "usesSimulation": false,
  "usesStochastic": false,
  "isNpHard": false
}
```

复杂度级别固定为：

- `L0`：手算、量纲、极限或解析检查；
- `L1`：经典确定性基线；
- `L2`：确定性数值模型或结构化优化；
- `L3`：复杂机理、分解或混合模型；
- `L4`：随机、启发式或机器学习路线。

当 `usesSimulation=true` 时，增加 `simulationPurpose` 和已核验的 `simulationEvidenceIds`。当 `usesStochastic=true` 时，增加整数 `seed`、不少于 5 的 `repetitions`、`convergence` 和 `dispersion`。当 `isNpHard=true` 时，`simplifications` 每项必须包含 `statement`、`basis` 和已核验的 `validationEvidenceIds`。

## 证据状态规则

- `verified`：已回读题面/来源，或已运行代码并保存产物，且定位信息有效。
- `provisional`：逻辑上合理但尚未验证；可以保留在草稿账本，不能成为最终主张。
- `failed`：已被反例、检验或运行结果否定；必须从最终结论撤回。

搜索命中、代码草稿、模型自述和漂亮图形都不是运行证据。审计 PASS 只说明过程账本自洽且证据引用完整，不自动证明数学推导正确，也不保证竞赛奖项；仍需人工复核题意、公式、代码和最终 PDF。
