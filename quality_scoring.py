from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote


RUBRIC_VERSION = "2026.4"
DEFAULT_QUALITY_THRESHOLD = 82
NUMERIC_VALUE = r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?"
ROUTING_TOOL_NAMES = {
    "search_skills",
    "read_skill",
    "search_materials",
    "origin_status",
    "detect_matlab_toolboxes",
}
SOURCE_TOOL_NAMES = {"read_material"}

MODE_WEIGHTS: dict[str, dict[str, int]] = {
    "solver": {
        "understanding": 20,
        "modeling": 25,
        "evidence": 18,
        "validation": 15,
        "communication": 12,
        "integrity": 10,
    },
    "cumcm": {
        "understanding": 15,
        "modeling": 20,
        "evidence": 20,
        "validation": 20,
        "communication": 15,
        "integrity": 10,
    },
    "paper": {
        "understanding": 12,
        "modeling": 15,
        "evidence": 23,
        "validation": 18,
        "communication": 22,
        "integrity": 10,
    },
    "reviewer": {
        "understanding": 20,
        "modeling": 15,
        "evidence": 20,
        "validation": 20,
        "communication": 15,
        "integrity": 10,
    },
}

DIMENSION_LABELS = {
    "understanding": "问题理解与任务覆盖",
    "modeling": "模型与数学严谨性",
    "evidence": "证据与可复现性",
    "validation": "验证、稳健性与决策边界",
    "communication": "表达与交付质量",
    "integrity": "真实性与风险控制",
}


def rubric_spec() -> dict[str, Any]:
    return {
        "version": RUBRIC_VERSION,
        "defaultThreshold": DEFAULT_QUALITY_THRESHOLD,
        "gradeBands": [
            {"minimum": 90, "grade": "A", "label": "竞赛交付级"},
            {"minimum": 82, "grade": "B", "label": "可交付"},
            {"minimum": 70, "grade": "C", "label": "需要修订"},
            {"minimum": 0, "grade": "D", "label": "不可交付"},
        ],
        "dimensions": [
            {
                "id": key,
                "label": label,
                "description": description,
            }
            for key, label, description in (
                ("understanding", DIMENSION_LABELS["understanding"], "子问题、目标、变量、约束和结论是否覆盖用户任务。"),
                ("modeling", DIMENSION_LABELS["modeling"], "模型选择、公式、目标函数、算法和基线比较是否匹配问题本质。"),
                ("evidence", DIMENSION_LABELS["evidence"], "数值、代码、表图、工具结果和引用能否支撑主张并复现。"),
                ("validation", DIMENSION_LABELS["validation"], "交叉验证、敏感性、不确定性、泄漏检查和适用边界是否充分。"),
                ("communication", DIMENSION_LABELS["communication"], "结构是否清楚、结论是否可执行、交付物是否明确。"),
                ("integrity", DIMENSION_LABELS["integrity"], "是否区分方案与真实运行结果，是否避免伪造和过度承诺。"),
            )
        ],
        "modeWeights": MODE_WEIGHTS,
        "hardGates": [
            {"id": "data_inspection", "cap": 55, "description": "有附件却未执行数据预检。"},
            {"id": "unsupported_execution", "cap": 70, "description": "声称已运行或已验证，但无成功工具或产物证据。"},
            {"id": "required_code", "cap": 72, "description": "明确要求代码实现，但没有代码或代码产物。"},
            {"id": "required_figures", "cap": 75, "description": "明确要求图表，但没有图形产物或可执行图表方案。"},
            {"id": "required_risk", "cap": 80, "description": "明确要求风险检查，但没有局限或风险边界。"},
            {"id": "optimization_feasibility", "cap": 78, "description": "给出最优解或优化结果，却没有报告可行性或约束违反量。"},
            {"id": "optimization_comparison", "cap": 80, "description": "竞赛整题给出优化结果，却没有数值基线、理论界、最优间隙或独立算法比较。"},
            {"id": "global_optimality", "cap": 76, "description": "声称得到全局最优，却没有给出可验证的全局最优性依据。"},
            {"id": "stochastic_robustness", "cap": 79, "description": "随机优化给出数值方案，却没有至少 3 次多种子运行、数值离散统计及停止/收敛证据。"},
            {"id": "predictive_validation", "cap": 78, "description": "给出预测结果，却没有结构正确的样本外验证和数值误差指标。"},
            {"id": "mechanistic_consistency", "cap": 80, "description": "机理模型给出数值结果，却没有明确量纲一致性及数值初边值/守恒/收敛校验。"},
            {"id": "abstract_numeric_evidence", "cap": 80, "description": "正式摘要没有为已分列的子问题给出可核对的量化结果。"},
            {"id": "artifact_link_integrity", "cap": 70, "description": "回答链接了后端未登记或不存在的任务产物。"},
            {"id": "minimum_content", "cap": 75, "description": "内容短到不足以支撑任务。"},
        ],
    }


@dataclass(frozen=True)
class DimensionScore:
    key: str
    score: int
    evidence: tuple[str, ...]


class QualityEvaluator:
    def __init__(self, threshold: int = DEFAULT_QUALITY_THRESHOLD) -> None:
        self.threshold = max(60, min(int(threshold), 95))

    def evaluate(
        self,
        *,
        mode: str,
        prompt: str,
        answer: str,
        meta: dict[str, Any] | None = None,
        tool_history: list[dict[str, Any]] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        revision: int = 0,
    ) -> dict[str, Any]:
        meta = meta or {}
        tool_history = tool_history or []
        artifacts = artifacts or []
        weights = MODE_WEIGHTS.get(mode, MODE_WEIGHTS["solver"])
        text = answer.strip()
        successful_tools = [item for item in tool_history if item.get("ok")]
        source_tools = [
            item
            for item in successful_tools
            if str(item.get("name", "")) in SOURCE_TOOL_NAMES and item.get("grounded", True)
        ]
        evidence_tools = [
            item
            for item in successful_tools
            if str(item.get("name", "")) not in ROUTING_TOOL_NAMES | SOURCE_TOOL_NAMES
        ]
        tool_names = {str(item.get("name", "")) for item in successful_tools}
        artifact_names = {
            str(item.get("name", ""))
            for item in artifacts
            if isinstance(item, dict) and item.get("name")
        }
        for item in successful_tools:
            for artifact in item.get("artifacts", []) if isinstance(item.get("artifacts"), list) else []:
                if isinstance(artifact, dict) and artifact.get("name"):
                    artifact_names.add(str(artifact["name"]))

        dimensions = [
            self._understanding(mode, prompt, text),
            self._modeling(mode, text, meta),
            self._evidence(text, evidence_tools, source_tools, artifact_names, meta),
            self._validation(mode, text),
            self._communication(mode, text),
            self._integrity(text, evidence_tools, source_tools, artifact_names, meta),
        ]
        dimension_map = {item.key: item for item in dimensions}
        uncapped = round(
            sum(dimension_map[key].score * weight / 100 for key, weight in weights.items()),
            1,
        )
        gates = self._gates(mode, text, meta, tool_names, evidence_tools, artifact_names)
        active_caps = [int(item["cap"]) for item in gates if not item["passed"]]
        cap = min(active_caps, default=100)
        total = min(uncapped, float(cap))

        issues: list[str] = [str(item["message"]) for item in gates if not item["passed"]]
        for item in sorted(dimensions, key=lambda dimension: dimension.score):
            if item.score < 70:
                issues.append(self._dimension_issue(item.key))
        issues = list(dict.fromkeys(issues))[:6]

        strengths = []
        for item in sorted(dimensions, key=lambda dimension: dimension.score, reverse=True):
            if item.score >= 78 and item.evidence:
                strengths.append(f"{DIMENSION_LABELS[item.key]}：{item.evidence[0]}")
        strengths = strengths[:4]

        report_dimensions = []
        for key, weight in weights.items():
            item = dimension_map[key]
            report_dimensions.append(
                {
                    "id": key,
                    "label": DIMENSION_LABELS[key],
                    "weight": weight,
                    "score": item.score,
                    "points": round(item.score * weight / 100, 1),
                    "evidence": list(item.evidence),
                }
            )

        return {
            "version": RUBRIC_VERSION,
            "mode": mode,
            "revision": revision,
            "threshold": self.threshold,
            "uncappedTotal": uncapped,
            "cap": cap,
            "total": total,
            "passed": total >= self.threshold,
            "grade": self._grade(total),
            "dimensions": report_dimensions,
            "gates": gates,
            "issues": issues,
            "strengths": strengths,
            "recommendations": [self._recommendation(issue) for issue in issues[:4]],
            "metrics": {
                "characters": len(text),
                "headings": len(re.findall(r"(?m)(?:^#{1,4}\s+|^\*\*[^*]+\*\*$)", text)),
                "codeBlocks": text.count("```") // 2,
                "numericClaims": len(re.findall(r"(?<!\w)-?\d+(?:\.\d+)?%?", text)),
                "successfulTools": len(successful_tools),
                "evidenceTools": len(evidence_tools),
                "sourceTools": len(source_tools),
                "artifacts": len(artifact_names),
            },
        }

    @staticmethod
    def _has(text: str, pattern: str) -> bool:
        return re.search(pattern, text, re.IGNORECASE) is not None

    @classmethod
    def _has_affirmed(cls, text: str, pattern: str) -> bool:
        """Match reported evidence, excluding nearby explicit negation.

        The evaluator is intentionally conservative: phrases such as “未报告 RMSE”、
        “测试集未设置” or “没有全局上界” must not satisfy an evidence gate merely
        because the keyword is present.
        """
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if cls._evidence_is_affirmed(text, match.start(), match.end()):
                return True
        return False

    @staticmethod
    def _evidence_is_affirmed(text: str, start: int, end: int) -> bool:
        separators = r"[。！？!?；;\n，,]|但是|然而|不过|(?<!不)但"
        negative_left = re.compile(
            r"(?:未曾?|没有|并未|尚未|缺少|缺乏|"
            r"不(?:含|包含|提供|报告|进行|做|设置|验证|检查|比较|运行|给出)).{0,8}$",
            re.IGNORECASE,
        )
        negative_right = re.compile(
            r"^.{0,8}(?:未|没有|尚未|缺失|缺少|不足|"
            r"不(?:通过|存在|可用|完整|充分|运行|报告|设置|验证|检查|比较))",
            re.IGNORECASE,
        )
        left_window = text[max(0, start - 36) : start]
        right_window = text[end : min(len(text), end + 36)]
        left_clause = re.split(separators, left_window)[-1]
        right_clause = re.split(separators, right_window)[0]
        if negative_left.search(left_clause) or negative_right.search(right_clause):
            return False
        evidence_clause = f"{left_clause}{text[start:end]}{right_clause}"
        if re.search(r"示例|演示|占位|待替换|待补充|待验证|假设值|仅用于说明", evidence_clause):
            return False
        return True

    @classmethod
    def _has_multiple_runs(cls, text: str) -> bool:
        repeat_patterns = (
            r"(?:使用|采用|共)?\s*(\d+)\s*个不同随机种子",
            r"(?:不同随机种子|独立重复|多种子运行)[^。；\n]{0,16}?(?:n\s*=\s*)?(\d+)\s*(?:次|组|轮|runs?)",
            r"(?:独立重复|重复运行)[^。；\n]{0,10}?(\d+)\s*(?:次|组|轮|runs?)",
        )
        for pattern in repeat_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                if int(match.group(1)) >= 3 and cls._evidence_is_affirmed(text, match.start(), match.end()):
                    return True
        seed_lists = re.finditer(
            r"(?:随机)?种子(?:列表)?\s*(?:为|=|:)\s*[\[(]?\s*(\d+(?:\s*[,，]\s*\d+){2,})",
            text,
            re.IGNORECASE,
        )
        return any(
            len(re.findall(r"\d+", match.group(1))) >= 3
            and cls._evidence_is_affirmed(text, match.start(), match.end())
            for match in seed_lists
        )

    @staticmethod
    def _extract_abstract(text: str) -> str:
        patterns = (
            r"(?ms)^#{1,4}\s*(?:摘要|Abstract)\s*$\s*(.*?)(?=^#{1,4}\s|\Z)",
            r"(?s)\\begin\{abstract\}(.*?)\\end\{abstract\}",
            r"(?ms)^摘\s*要\s*$\s*(.*?)(?=^\s*(?:关键词|一[、.]|1[、.])|\Z)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    @classmethod
    def _abstract_evidence(cls, abstract: str) -> tuple[int, int]:
        if not abstract:
            return 0, 0
        labels = set(
            re.findall(
                r"(?:问题|第)\s*([一二三四五六七八九十]|[1-9])(?:问)?",
                abstract,
            )
        )
        required = max(1, len(labels))
        unit = (
            r"%|秒|分钟|小时|毫秒|米|千米|厘米|毫米|千克|公斤|吨|元|万元|"
            r"摄氏度|℃|°C|MW|kW|W|m/s|km/h|kg|t|s(?![A-Za-z])"
        )
        metric = (
            r"目标值|目标函数|总时长|时长|误差|残差|准确率|召回率|覆盖率|可行率|"
            r"功率|收益|成本|温度|速度|产量|数量|相关系数|R\^?2|R²|MAE|RMSE|MAPE|AUC|F1"
        )
        patterns = (
            rf"(?:{metric})[^。；\n]{{0,18}}(?:为|=|达到|提升至|降低至)\s*{NUMERIC_VALUE}\s*(?:{unit})?",
            rf"{NUMERIC_VALUE}\s*(?:{unit})",
        )
        spans: list[tuple[int, int]] = []
        for pattern in patterns:
            for match in re.finditer(pattern, abstract, re.IGNORECASE):
                if not cls._evidence_is_affirmed(abstract, match.start(), match.end()):
                    continue
                if any(match.start() < end and match.end() > start for start, end in spans):
                    continue
                spans.append((match.start(), match.end()))
        return len(spans), required

    def _understanding(self, mode: str, prompt: str, text: str) -> DimensionScore:
        score = 32
        evidence = []
        if self._has(text, r"问题|任务|目标|需求"):
            score += 12
            evidence.append("明确回应了任务或目标")
        subquestions = len(
            re.findall(r"(?m)(?:问题\s*[一二三四五六七八九0-9]|^\s*\d+[.、])", text)
        )
        if subquestions >= 2:
            score += 16
            evidence.append("按子问题组织回答")
        if self._has(text, r"假设|前提|条件"):
            score += 10
            evidence.append("说明了假设或前提")
        if self._has(text, r"变量|符号|参数"):
            score += 10
            evidence.append("定义了变量或参数")
        if self._has(text, r"约束|边界|适用范围"):
            score += 10
            evidence.append("识别了约束与边界")
        if self._has(text, r"结论|建议|推荐|决策"):
            score += 10
            evidence.append("给出了结论或决策建议")
        prompt_terms = self._prompt_terms(prompt)
        if prompt_terms:
            covered = sum(term in text.lower() for term in prompt_terms)
            if covered / len(prompt_terms) >= 0.35:
                score += 10
                evidence.append("覆盖了用户内容中的关键概念")
        if mode == "reviewer" and self._has(text, r"严重|高风险|中风险|低风险|修复"):
            score += 10
            evidence.append("审查结果包含严重度和修复动作")
        return DimensionScore("understanding", min(score, 100), tuple(evidence))

    def _modeling(self, mode: str, text: str, meta: dict[str, Any]) -> DimensionScore:
        score = 38 if mode == "paper" else 30
        evidence = []
        if self._has(text, r"回归|优化|仿真|规划|聚类|分类|时间序列|AFT|随机森林|贝叶斯|网络流|模型"):
            score += 14
            evidence.append("给出了可识别的模型路线")
        if self._has(text, r"\$[^$]+\$|\\\[|\\begin\{equation|目标函数|arg\s*min|arg\s*max"):
            score += 15
            evidence.append("包含数学表达或目标函数")
        if self._has(text, r"约束|可行域|边界条件|守恒|非负"):
            score += 10
            evidence.append("说明了约束或可行性")
        if self._has_affirmed(text, r"基线|对照|备选|比较|AIC|BIC|交叉验证"):
            score += 12
            evidence.append("比较了模型或基线")
        if self._has(text, r"算法|步骤|迭代|求解器|复杂度|伪代码"):
            score += 10
            evidence.append("说明了求解过程")
        if self._has_affirmed(text, r"量纲|单位一致|初始条件|边界条件|守恒|极限情形"):
            score += 8
            evidence.append("检查了机理一致性或初边值条件")
        if self._has_affirmed(text, r"理论上界|理论下界|最优间隙|松弛界|独立算法|多初值"):
            score += 8
            evidence.append("用理论界或独立路线标定求解质量")
        requirements = set(meta.get("requirements", []))
        if "代码实现" in requirements and "```" in text:
            score += 12
            evidence.append("提供了代码实现")
        if mode == "reviewer" and self._has(text, r"泄漏|不可辨识|不可行|过拟合|偏差|冲突"):
            score += 15
            evidence.append("识别了模型逻辑风险")
        return DimensionScore("modeling", min(score, 100), tuple(evidence))

    def _evidence(
        self,
        text: str,
        successful_tools: list[dict[str, Any]],
        source_tools: list[dict[str, Any]],
        artifacts: set[str],
        meta: dict[str, Any],
    ) -> DimensionScore:
        score = 24
        evidence = []
        numeric_claims = len(re.findall(r"(?<!\w)-?\d+(?:\.\d+)?%?", text))
        if numeric_claims >= 3:
            score += 15
            evidence.append("包含可核对的数值结果")
        if successful_tools:
            score += min(22, 8 + len(successful_tools) * 4)
            evidence.append(f"引用了 {len(successful_tools)} 次成功工具执行")
        if source_tools:
            score += min(16, 6 + len(source_tools) * 4)
            evidence.append(f"检索或读取了 {len(source_tools)} 次本地来源资料")
        if artifacts:
            score += min(18, 8 + len(artifacts) * 2)
            evidence.append(f"生成了 {len(artifacts)} 个可下载产物")
        if self._has(text, r"```|\|\s*---\s*\||表\s*\d|图\s*\d"):
            score += 10
            evidence.append("使用代码、表格或图形承载证据")
        if self._has(text, r"数据|样本|残差|系数|置信区间|p\s*[值=]|AUC|RMSE|MAE|R\^?2"):
            score += 12
            evidence.append("主张关联到数据或统计量")
        if self._has(text, r"https?://|DOI|PMID|参考文献|引用"):
            score += 8
            evidence.append("提供了来源或引用线索")
        if meta.get("uploads") and any(item.get("name") == "inspect_dataset" for item in successful_tools):
            score += 10
            evidence.append("附件在建模前经过预检")
        return DimensionScore("evidence", min(score, 100), tuple(evidence))

    def _validation(self, mode: str, text: str) -> DimensionScore:
        score = 30 if mode == "reviewer" else 22
        evidence = []
        if self._has_affirmed(text, r"交叉验证|验证集|测试集|折外|留一|Bootstrap|自助法"):
            score += 18
            evidence.append("包含样本外或重抽样验证")
        if self._has_affirmed(text, r"敏感性|稳健性|鲁棒性|情景分析|扰动"):
            score += 16
            evidence.append("检查了敏感性或稳健性")
        if self._has_affirmed(text, r"置信区间|不确定性|误差传播|标准误|分位数"):
            score += 14
            evidence.append("量化了不确定性")
        if self._has_affirmed(text, r"泄漏|分组验证|同一.*不跨|时间顺序|决策前"):
            score += 14
            evidence.append("检查了数据泄漏或验证单位")
        if self._has(text, r"局限|风险|适用范围|不能外推|边界|不足"):
            score += 14
            evidence.append("明确了局限和适用边界")
        if self._has_affirmed(text, r"AUC|PR-AUC|召回率|特异度|RMSE|MAE|残差|拟合优度|覆盖率"):
            score += 12
            evidence.append("使用了任务匹配的评价指标")
        if self._has_affirmed(text, r"步长收敛|网格收敛|约束违反|最大违反量|多随机种子|独立重复"):
            score += 12
            evidence.append("报告了数值稳定性或约束审计")
        return DimensionScore("validation", min(score, 100), tuple(evidence))

    def _communication(self, mode: str, text: str) -> DimensionScore:
        score = 36
        evidence = []
        headings = len(re.findall(r"(?m)(?:^#{1,4}\s+|^\*\*[^*]+\*\*$)", text))
        if headings >= 2:
            score += 14
            evidence.append("使用清楚的层级结构")
        if 450 <= len(text) <= 12_000:
            score += 14
            evidence.append("篇幅与完整度较平衡")
        elif len(text) >= 220:
            score += 7
        if self._has(text, r"结论|最终|建议|推荐|下一步"):
            score += 12
            evidence.append("结论或下一步明确")
        if self._has(text, r"(?m)(?:^\s*[-*]\s+|^\s*\d+[.、]\s*)"):
            score += 10
            evidence.append("步骤或要点易于扫描")
        if self._has(text, r"下载|产物|文件|代码|表格|图"):
            score += 8
            evidence.append("交付物表达清楚")
        if not self._has(text, r"作为AI|作为一个AI|下面是提示词|供另一个Agent"):
            score += 6
        if mode == "reviewer" and self._has(text, r"位置|风险|修复|建议"):
            score += 12
            evidence.append("审查意见包含定位、风险和修复")
        if len(text) > 18_000:
            score -= 10
        return DimensionScore("communication", max(0, min(score, 100)), tuple(evidence))

    def _integrity(
        self,
        text: str,
        successful_tools: list[dict[str, Any]],
        source_tools: list[dict[str, Any]],
        artifacts: set[str],
        meta: dict[str, Any],
    ) -> DimensionScore:
        score = 72
        evidence = []
        if self._has(text, r"假设|待验证|需要补充|信息不足|无法确认"):
            score += 12
            evidence.append("区分了假设和已知事实")
        if self._has(text, r"局限|不构成|不能外推|仅适用于|风险"):
            score += 12
            evidence.append("给出了明确风险边界")
        if successful_tools or artifacts:
            score += 8
            evidence.append("运行性主张有工具或产物支撑")
        if source_tools:
            score += 5
            evidence.append("资料性主张有本地来源支撑")
        claims_execution = self._has(
            text,
            r"已经?运行|运行结果(?:为|显示|如下)|实跑(?:得到|结果)|已经?验证(?:通过|完成)?|已经?生成|已经?导出",
        )
        if claims_execution and not successful_tools and not artifacts:
            score -= 35
        if self._has(text, r"TODO|TBD|待补充|占位符|xxx"):
            score -= 20
        if self._has(text, r"100%准确|完全证明|必然正确|绝对可靠"):
            score -= 18
        if meta.get("uploads") and not successful_tools:
            score -= 12
        return DimensionScore("integrity", max(0, min(score, 100)), tuple(evidence))

    def _gates(
        self,
        mode: str,
        text: str,
        meta: dict[str, Any],
        tool_names: set[str],
        successful_tools: list[dict[str, Any]],
        artifacts: set[str],
    ) -> list[dict[str, Any]]:
        requirements = set(meta.get("requirements", []))
        has_uploads = bool(meta.get("uploads"))
        inspected = "inspect_dataset" in tool_names
        has_code = "```" in text or any(name.endswith((".py", ".m", ".ipynb")) for name in artifacts)
        has_figure = any(
            name.lower().endswith((".png", ".svg"))
            or (
                name.lower().endswith(".pdf")
                and self._has(name, r"fig|figure|plot|chart|图")
            )
            for name in artifacts
        )
        has_figure_plan = self._has(text, r"图\s*\d|图表|横轴|纵轴|可视化|绘图")
        has_risk = self._has(text, r"风险|局限|不足|适用范围|不能外推|敏感性")
        execution_claim = self._has(
            text,
            r"已经?运行|运行结果(?:为|显示|如下)|实跑(?:得到|结果)|已经?验证(?:通过|完成)?|已经?生成|已经?导出",
        )
        optimization_result_claim = self._has(
            text,
            r"(?:最优解|最优方案|优化结果)\s*(?:为|是|[:：])|(?<!未)(?<!未能)(?<!没有)(?<!不能)(?<!无法)(?:求得|得到|获得).{0,12}(?:最优解|最优方案)",
        )
        has_feasibility_evidence = self._has_affirmed(
            text,
            rf"(?:最大)?(?:约束违反量|约束残差|不可行度|max(?:imum)?\s+violation)"
            rf"\s*(?:为|=|:|≤|<)\s*{NUMERIC_VALUE}|可行率\s*(?:为|=|:)\s*100(?:\.0+)?\s*%",
        )
        global_optimum_claim = self._has(
            text,
            r"(?<!未)(?<!未能)(?<!没有)(?<!不能)(?<!无法)(?:求得|得到|获得|达到).{0,12}全局最优|(?:已经|严格)证明.{0,8}全局最优|全局最优(?:解|方案|值)\s*(?:为|是|[:：])",
        )
        zero_gap_certificate = self._has_affirmed(
            text,
            r"(?:最优性间隙|MIP\s*gap|relative\s+gap)\s*(?:为|=|:|≤)\s*0+(?:\.0+)?\s*%?",
        )
        proof_certificate = self._has_affirmed(
            text,
            r"穷举证明|分支定界.{0,18}(?:证明最优|返回最优)|凸性.{0,18}(?:证明|保证).{0,10}(?:全局最优|充分)|"
            r"KKT.{0,18}充分|(?:目标值|可行解).{0,24}(?:等于|达到).{0,12}(?:全局上界|全局下界|对偶界)",
        )
        has_global_certificate = zero_gap_certificate or proof_certificate
        numeric_baseline = self._has_affirmed(
            text,
            rf"(?:贪心|现状|原方案|均值规则|零规则|持久性|基线|对照方案)[^。；\n]{{0,45}}"
            rf"(?:目标值|得分|时长|误差|RMSE|MAE|AUC)?\s*(?:为|=|:)\s*{NUMERIC_VALUE}",
        )
        numeric_improvement = self._has_affirmed(
            text,
            rf"(?:较|相对|相比)[^。；\n]{{0,30}}(?:提升|降低|减少|增加|改善)\s*(?:了)?\s*{NUMERIC_VALUE}\s*%",
        )
        numeric_bound_or_gap = self._has_affirmed(
            text,
            rf"(?:(?:LP|线性|拉格朗日|对偶|松弛|理论|可证)?(?:上界|下界|best\s+bound)|"
            rf"(?:最优性间隙|最优间隙|MIP\s*gap|relative\s+gap))\s*(?:为|=|:|≤|<)\s*{NUMERIC_VALUE}\s*%?",
        )
        numeric_independent_check = self._has_affirmed(
            text,
            rf"(?:独立算法|第二算法|另一算法|两种算法|多初值)[^。；\n]{{0,55}}"
            rf"(?:相差|差异|目标值|最优值|范围)\s*(?:为|=|:|≤|<)?\s*{NUMERIC_VALUE}\s*%?",
        )
        has_optimization_comparison = any(
            (numeric_baseline, numeric_improvement, numeric_bound_or_gap, numeric_independent_check)
        )
        stochastic_algorithm = self._has(
            text,
            r"遗传算法|模拟退火|粒子群|蚁群|差分进化|随机搜索|随机优化|NSGA(?:-?II|-?III)?|"
            r"genetic algorithm|simulated annealing|particle swarm",
        )
        stochastic_result_claim = stochastic_algorithm and self._has(
            text,
            r"(?:结果|方案|目标值|最优值).{0,12}(?:为|是|[:：=])|(?:得到|获得|求得).{0,12}(?:解|方案|目标值)",
        )
        has_multiple_seed_runs = self._has_multiple_runs(text)
        has_stochastic_dispersion = self._has_affirmed(
            text,
            rf"(?:标准差|std|变异系数|CV|四分位距|IQR|极差|最差值|成功率)"
            rf"\s*(?:为|=|:)\s*{NUMERIC_VALUE}\s*%?|"
            rf"中位数[^。；\n]{{0,18}}(?:四分位距|IQR)[^。；\n]{{0,12}}(?:为|=|:)\s*{NUMERIC_VALUE}"
            rf"[^。；\n]{{0,12}}{NUMERIC_VALUE}",
        )
        has_stochastic_convergence = self._has_affirmed(
            text,
            rf"(?:收敛容差|停止阈值|目标改变量|终止残差|收敛代数|gap)"
            rf"\s*(?:为|=|:|≤|<)\s*{NUMERIC_VALUE}",
        ) or any(
            re.search(r"convergence|trace|收敛", name, re.IGNORECASE)
            and name.lower().endswith((".png", ".svg", ".pdf", ".csv", ".json"))
            for name in artifacts
        )
        predictive_result_claim = self._has(
            text,
            r"(?:预测|预报|分类).{0,18}(?:结果|数值|准确率|AUC|RMSE|MAE|MAPE).{0,10}(?:为|是|[:：=])|"
            r"(?:预测得到|预测为)",
        )
        has_out_of_sample_design = self._has_affirmed(
            text,
            r"按(?:主体|患者|企业|站点|年份|时间|地区|设备)[^。；\n]{0,12}(?:划分|分组|验证)|"
            r"GroupKFold|TimeSeriesSplit|滚动(?:窗口|验证)|walk[- ]?forward|时间外推|"
            r"分层(?:抽样|划分)|留一法|回测|backtest",
        )
        has_predictive_metric = self._has_affirmed(
            text,
            rf"(?:测试集|验证集|折外|样本外|out[- ]of[- ]sample)[^。；\n]{{0,80}}"
            rf"(?:RMSE|MAE|MAPE|SMAPE|AUC|PR-AUC|准确率|召回率|特异度|F1|Brier|对数损失|覆盖率)"
            rf"\s*(?:为|=|:)\s*{NUMERIC_VALUE}\s*%?",
        )
        mechanistic_model = self._has(
            text,
            r"机理模型|热传导|微分方程|动力学|运动学|轨迹模型|受力分析|传质|传热|"
            r"能量守恒|质量守恒|ODE|PDE",
        )
        mechanistic_result_claim = mechanistic_model and self._has(
            text,
            r"(?:计算|求解|仿真|模型).{0,12}(?:结果|得到|表明)|数值解|(?:温度|位置|速度|轨迹|功率).{0,10}(?:为|是|[:：=])",
        )
        has_dimension_audit = self._has_affirmed(
            text,
            r"(?:方程|等式|各项|左右两端)[^。；\n]{0,30}(?:量纲|单位)[^。；\n]{0,12}(?:一致|相同)|"
            r"量纲(?:检查|分析)[^。；\n]{0,12}(?:通过|一致)",
        )
        has_mechanistic_check = self._has_affirmed(
            text,
            rf"(?:守恒|初值|边界|极限|解析解|解析特例|几何|步长|网格)[^。；\n]{{0,40}}"
            rf"(?:残差|误差|相对差|变化率)[^。；\n]{{0,10}}(?:为|=|:|≤|<)\s*{NUMERIC_VALUE}\s*%?",
        )
        abstract = self._extract_abstract(text)
        abstract_evidence_count, abstract_required_count = self._abstract_evidence(abstract)
        linked_artifacts = {
            unquote(name)
            for name in re.findall(
                r"/api/artifacts/[a-f0-9]{32}/([^\s)\]}>\"'?#]+)",
                text,
                flags=re.IGNORECASE,
            )
        }
        missing_linked_artifacts = linked_artifacts - artifacts
        depth = str(meta.get("depth", ""))
        minimum_characters = 120 if depth == "简要" else 180 if mode in {"paper", "reviewer"} else 220
        gates = [
            self._gate(
                "data_inspection",
                not has_uploads or inspected,
                55,
                "存在数据附件，但回答前没有成功执行 inspect_dataset。",
            ),
            self._gate(
                "unsupported_execution",
                not execution_claim or bool(successful_tools) or bool(artifacts),
                70,
                "回答声称已经运行或生成结果，但后端没有成功工具或产物记录。",
            ),
            self._gate(
                "required_code",
                "代码实现" not in requirements or has_code,
                72,
                "用户明确要求代码实现，但最终回答没有代码块或代码产物。",
            ),
            self._gate(
                "required_figures",
                "图表方案" not in requirements or has_figure or has_figure_plan,
                75,
                "用户明确要求图表，但最终回答没有图形产物或可执行图表方案。",
            ),
            self._gate(
                "required_risk",
                "风险检查" not in requirements or has_risk,
                80,
                "用户明确要求风险检查，但最终回答没有局限、敏感性或适用边界。",
            ),
            self._gate(
                "optimization_feasibility",
                mode == "reviewer" or not optimization_result_claim or has_feasibility_evidence,
                78,
                "回答给出最优解或优化结果，但没有报告可行性、约束残差或最大违反量。",
            ),
            self._gate(
                "optimization_comparison",
                mode not in {"cumcm", "paper"} or not optimization_result_claim or has_optimization_comparison,
                80,
                "竞赛整题给出优化结果，但没有用基线、理论界、最优间隙、多初值或独立算法标定解的质量。",
            ),
            self._gate(
                "global_optimality",
                mode == "reviewer" or not global_optimum_claim or has_global_certificate,
                76,
                "回答声称得到全局最优，但没有全局界、最优间隙、穷举/分支定界或充分最优性证明。",
            ),
            self._gate(
                "stochastic_robustness",
                mode == "reviewer"
                or not stochastic_result_claim
                or (has_multiple_seed_runs and has_stochastic_dispersion and has_stochastic_convergence),
                79,
                "随机优化给出了数值方案，但没有报告至少 3 次多种子独立运行、数值离散统计和停止/收敛证据。",
            ),
            self._gate(
                "predictive_validation",
                mode == "reviewer"
                or not predictive_result_claim
                or (has_out_of_sample_design and has_predictive_metric),
                78,
                "回答给出预测结果，但没有说明尊重主体/时间结构的验证设计并报告数值样本外误差。",
            ),
            self._gate(
                "mechanistic_consistency",
                mode == "reviewer"
                or not mechanistic_result_claim
                or (has_dimension_audit and has_mechanistic_check),
                80,
                "机理模型给出了数值结果，但没有同时报告明确的量纲一致性及数值初边值、守恒、极限或收敛误差。",
            ),
            self._gate(
                "abstract_numeric_evidence",
                mode not in {"cumcm", "paper"}
                or not abstract
                or abstract_evidence_count >= abstract_required_count,
                80,
                f"正式摘要识别到 {abstract_required_count} 个结果单元，但仅有 {abstract_evidence_count} 个带指标或单位的量化结果。",
            ),
            self._gate(
                "artifact_link_integrity",
                not missing_linked_artifacts,
                70,
                "回答包含后端未登记的任务产物链接；只能链接成功工具实际返回的 artifacts。",
            ),
            self._gate(
                "minimum_content",
                len(text) >= minimum_characters,
                60 if len(text) < max(80, minimum_characters // 2) else 75,
                f"回答内容过短，当前任务至少需要约 {minimum_characters} 字支撑结论。",
            ),
        ]
        return gates

    @staticmethod
    def _gate(gate_id: str, passed: bool, cap: int, message: str) -> dict[str, Any]:
        return {"id": gate_id, "passed": passed, "cap": cap, "message": message}

    @staticmethod
    def _prompt_terms(prompt: str) -> list[str]:
        user_content = prompt.partition("用户内容：")[2] or prompt
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,6}", user_content.lower())
        stop = {"请分析", "完成", "这个", "进行", "需要", "用户", "内容", "数据", "问题"}
        return list(dict.fromkeys(token for token in tokens if token not in stop))[:16]

    @staticmethod
    def _dimension_issue(key: str) -> str:
        return {
            "understanding": "任务覆盖不足，需要明确子问题、变量、约束和最终决策。",
            "modeling": "模型论证不足，需要补充模型选择依据、数学定义或求解过程。",
            "evidence": "证据链偏弱，需要用运行结果、数值、代码、表图或引用支撑主张。",
            "validation": "缺少验证与稳健性检查，需要补充样本外评价、不确定性或敏感性分析。",
            "communication": "结构或交付表达不够清楚，需要压实结论并标明可执行产物。",
            "integrity": "真实性边界不足，需要区分假设、计划与已经运行验证的结果。",
        }[key]

    @staticmethod
    def _recommendation(issue: str) -> str:
        return issue.replace("不足", "需补强").replace("缺少", "补充").replace("没有", "补充")

    @staticmethod
    def _grade(total: float) -> str:
        if total >= 90:
            return "A"
        if total >= 82:
            return "B"
        if total >= 70:
            return "C"
        return "D"
