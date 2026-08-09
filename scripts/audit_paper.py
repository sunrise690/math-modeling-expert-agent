from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {".md", ".tex", ".txt", ".pdf", ".docx"}
PLACEHOLDER_PATTERN = re.compile(
    r"TODO|TBD|待补充|待替换|占位符|这里插入|此处插入|xxx+|\?\?\?",
    re.IGNORECASE,
)
INTERPRETIVE_TERMS = r"表明|说明|原因是|意味着|可见|展示|显示|比较|标出|报告|揭示|反映|对应"
VALIDATION_TERMS = r"检验|验证|敏感性|稳健性|鲁棒性|残差|误差|收敛|回算|对照|基线|置信区间|扰动"
NUMERIC_TOKEN = r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*(?:[eE][-+]?\d+|×\s*10\^?\s*[-+]?\d+))?"
ACADEMIC_STYLE_TERMS: dict[str, str] = {
    "算法披露": "求解方法",
    "质量标定": "结果可靠性检验",
    "主口径": "中心视线判据或基准判据",
    "保守二次审计": "保守判据复核",
    "完整圆柱审计": "圆柱整体遮蔽判据复核",
    "工作簿回读": "结果表反算",
    "搜索记账": "搜索过程记录",
    "聊天记录": "计算输出",
    "终稿策略": "最终方案",
    "证据链": "模型、计算与验证过程",
    "向后接口": "与后续问题的联系",
    "图件主张": "图示结论",
    "候选包": "候选组合",
    "路线包": "同航路组合",
    "投放包": "同航路组合",
    "保留包": "保留的候选组合",
    "零平台": "目标函数为零的平台区域",
    "不直接信任优化器": "根据结果表重新计算约束",
    "不编造": "说明数据不足及相应分析边界",
}
Q_NOTATION_PATTERN = re.compile(r"(?<![A-Za-z0-9_])Q([1-9])(?![A-Za-z0-9_])", re.IGNORECASE)
CLI_Q_OPTION_PATTERN = re.compile(r"--Q[1-9](?:-[A-Za-z0-9_]+)+", re.IGNORECASE)


def _count_q_notation(text: str) -> int:
    """Count prose-style Q1--Q9 labels while ignoring reproducibility CLI flags."""
    prose = CLI_Q_OPTION_PATTERN.sub(" ", text)
    return len(Q_NOTATION_PATTERN.findall(prose))


def _read_docx(path: Path) -> tuple[str, dict[str, int]]:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    paragraphs = re.findall(r"<w:p\b.*?</w:p>", xml, flags=re.DOTALL)
    text = "\n".join(
        "".join(re.findall(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", paragraph, flags=re.DOTALL))
        for paragraph in paragraphs
    )
    text = re.sub(r"<[^>]+>", "", text)
    return text, {
        "embedded_figures": len(re.findall(r"<w:drawing\b|<w:pict\b", xml)),
        "embedded_tables": len(re.findall(r"<w:tbl\b", xml)),
    }


def _read_pdf(path: Path) -> tuple[str, dict[str, int]]:
    try:
        from pypdf import PdfReader
    except ImportError as error:  # pragma: no cover - dependency is bundled in production
        raise RuntimeError("审计 PDF 需要 pypdf") from error
    reader = PdfReader(str(path))
    text = "\n\f\n".join((page.extract_text() or "") for page in reader.pages)
    return text, {"pages": len(reader.pages)}


def _read_source(path: Path) -> tuple[str, dict[str, int]]:
    extension = path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("仅支持 Markdown、LaTeX、TXT、PDF 和 DOCX 论文")
    if extension == ".pdf":
        return _read_pdf(path)
    if extension == ".docx":
        return _read_docx(path)
    return path.read_text(encoding="utf-8-sig"), {}


def _strip_tex_comments(source: str) -> str:
    r"""Remove only unescaped TeX comments while preserving ``\%`` text."""
    rendered: list[str] = []
    for line in source.splitlines(keepends=True):
        cut_at: int | None = None
        for index, character in enumerate(line):
            if character != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut_at = index
                break
        if cut_at is None:
            rendered.append(line)
            continue
        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else "\r" if line.endswith("\r") else ""
        rendered.append(line[:cut_at] + newline)
    return "".join(rendered)


def _plain_text(source: str, extension: str) -> str:
    text = source
    if extension == ".tex":
        text = _strip_tex_comments(text)
        text = text.replace(r"\%", "%")
        text = re.sub(r"\\(?:cite|ref|label|eqref)\{[^}]*\}", " ", text)
        text = re.sub(r"\\(?:begin|end)\{[^}]*\}", " ", text)
        text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", text)
        text = text.replace("{", " ").replace("}", " ").replace("$", " ")
    elif extension == ".md":
        text = re.sub(r"!\[[^]]*\]\([^)]*\)", " ", text)
        text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
        text = re.sub(r"[`#>*_|~-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_abstract(source: str) -> str:
    patterns = (
        r"(?s)\\begin\{abstract\}(.*?)\\end\{abstract\}",
        r"(?ms)^#{1,4}\s*(?:摘要|Abstract)\s*$\s*(.*?)(?=^#{1,4}\s|\Z)",
        r"(?s)(?:^|\n)\s*摘\s*要\s*[:：]?\s*(.*?)(?=\n\s*(?:关键词|关键字|1[.、 ]|一[、.]))",
    )
    for pattern in patterns:
        match = re.search(pattern, source, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _section_spans(source: str, extension: str) -> list[tuple[str, str, int, int]]:
    if extension == ".tex":
        matches = list(re.finditer(r"\\section\*?\{([^}]+)\}", source))
    elif extension == ".md":
        matches = list(re.finditer(r"(?m)^#{1,2}\s+(.+?)\s*$", source))
    else:
        numeral = r"[一二三四五六七八九十0-9]+"
        matches = list(
            re.finditer(
                rf"(?m)^[ \t]*(?:第?\s*{numeral}\s*[、.．]?\s+)?"
                rf"(摘要|问题重述|问题分析[^。；\r\n]{{0,40}}|模型假设[^。；\r\n]{{0,40}}|"
                rf"符号说明|主要符号|模型建立[^。；\r\n]{{0,40}}|"
                rf"问题\s*{numeral}(?:\s*[:：][^。；\r\n]{{0,60}})?|"
                rf"模型检验[^。；\r\n]{{0,40}}|敏感性分析[^。；\r\n]{{0,40}}|"
                rf"模型评价[^。；\r\n]{{0,40}}|结论|参考文献)[ \t]*$",
                source,
            )
        )
    blocks: list[tuple[str, str, int, int]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        blocks.append((match.group(1).strip(), source[match.end() : end], match.start(), end))
    return blocks


def _section_blocks(source: str, extension: str) -> list[tuple[str, str]]:
    return [(title, body) for title, body, _start, _end in _section_spans(source, extension)]


def _question_index(title: str) -> int | None:
    match = re.search(r"(?:问题|第)\s*([一二三四五六七八九十0-9]+)", title)
    if not match:
        return None
    token = match.group(1)
    if token.isdigit():
        return int(token)
    mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    return mapping.get(token)


def _question_spans(source: str, extension: str) -> list[tuple[str, str, int, int]]:
    if extension in {".tex", ".md"}:
        return [item for item in _section_spans(source, extension) if _question_index(item[0]) is not None]

    numeral = r"[一二三四五六七八九十0-9]+"
    prefixed_question_pattern = (
        rf"(?m)^[ \t]*第?\s*{numeral}\s*[、.．]?\s+"
        rf"(问题\s*{numeral}(?:\s*[:：][^。；\r\n]{{0,60}})?)[ \t]*$"
    )
    question_matches = list(re.finditer(prefixed_question_pattern, source))
    require_prefix = bool(question_matches)
    if not question_matches:
        question_matches = list(
            re.finditer(
                rf"(?m)^[ \t]*(问题\s*{numeral}(?:\s*[:：][^。；\r\n]{{0,60}})?)[ \t]*$",
                source,
            )
        )
    terminal_prefix = rf"第?\s*{numeral}\s*[、.．]?\s+" if require_prefix else ""
    terminal_starts = [
        match.start()
        for match in re.finditer(
            rf"(?m)^[ \t]*(?:{terminal_prefix})?"
            rf"(?:跨问题|数值验证|模型评价|结论|参考文献|附录)[^。；\r\n]{{0,80}}[ \t]*$",
            source,
        )
    ]
    blocks: list[tuple[str, str, int, int]] = []
    for index, match in enumerate(question_matches):
        possible_ends = question_matches[index + 1 : index + 2]
        end_positions = [item.start() for item in possible_ends]
        end_positions.extend(position for position in terminal_starts if position > match.end())
        end = min(end_positions, default=len(source))
        blocks.append((match.group(1).strip(), source[match.end() : end], match.start(), end))
    return blocks


def _question_blocks(source: str, extension: str) -> list[tuple[str, str]]:
    return [(title, body) for title, body, _start, _end in _question_spans(source, extension)]


def _figure_records(source: str, extension: str, extras: dict[str, int]) -> tuple[int, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    if extension == ".tex":
        matches = list(
            re.finditer(
                r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}",
                source,
                flags=re.DOTALL,
            )
        )
        for index, match in enumerate(matches, start=1):
            block = match.group(1)
            caption_match = re.search(r"\\caption\{([^}]*)\}", block)
            label_match = re.search(r"\\label\{([^}]*)\}", block)
            records.append(
                {
                    "caption": caption_match.group(1).strip() if caption_match else "",
                    "label": label_match.group(1).strip() if label_match else str(index),
                    "start": match.start(),
                }
            )
        return len(matches), records
    if extension == ".md":
        matches = list(re.finditer(r"!\[([^]]*)\]\([^)]*\)", source))
        return len(matches), [
            {"caption": match.group(1).strip(), "label": str(index), "start": match.start()}
            for index, match in enumerate(matches, start=1)
        ]
    if extension == ".docx":
        matches = list(re.finditer(r"(?m)^\s*图\s*(\d+(?:[-—.]\d+)?)([^\n]*)", source))
        records = [
            {
                "caption": f"图 {match.group(1)}{match.group(2)}".strip(),
                "label": match.group(1),
                "start": match.start(),
            }
            for match in matches
        ]
        return extras.get("embedded_figures", len(records)), records

    numbered: dict[str, dict[str, Any]] = {}
    for match in re.finditer(r"(?m)^\s*图\s*(\d+(?:[-—.]\d+)?)([^\n]*)", source):
        label = match.group(1)
        candidate = f"图 {label}{match.group(2)}".strip()
        if len(candidate) > len(str(numbered.get(label, {}).get("caption", ""))):
            numbered[label] = {"caption": candidate, "label": label, "start": match.start()}
    records = list(numbered.values())
    return len(records), records


def _count_figures(source: str, extension: str, extras: dict[str, int]) -> tuple[int, list[str]]:
    count, records = _figure_records(source, extension, extras)
    return count, [str(record["caption"]) for record in records if record.get("caption")]


def _count_equations(source: str, extension: str) -> int:
    if extension == ".tex":
        return len(re.findall(r"\\begin\{(?:equation|align|gather|multline)\*?\}|\$\$|\\\[", source))
    if extension == ".md":
        return len(re.findall(r"\$\$|\\\[", source))
    # 成品 PDF/DOCX/TXT 已没有 LaTeX 环境标记。竞赛论文通常保留右端公式号，
    # 因此以行尾 (1)、(2)… 作为可审计代理；它只用于证据密度门禁，不推断公式正确性。
    return len(set(re.findall(r"(?m)\(\s*(\d{1,3})\s*\)[ \t]*$", source)))


def _count_figure_interpretations(
    source: str, extension: str, captions: list[str], figure_count: int
) -> int:
    def context(text: str, start: int, end: int) -> str:
        delimiters = ("。", "！", "？", ".", "!", "?")
        left = max(text.rfind(delimiter, 0, start) for delimiter in delimiters)
        right_candidates = [position for delimiter in delimiters if (position := text.find(delimiter, end)) >= 0]
        right = min(right_candidates, default=min(len(text), end + 180))
        return text[left + 1 : right + 1]

    discussed: set[str] = set()
    if extension == ".tex":
        blocks = re.findall(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", source, flags=re.DOTALL)
        labels = [match.group(1) for block in blocks if (match := re.search(r"\\label\{([^}]+)\}", block))]
        for label in labels:
            pattern = re.compile(
                rf"(?:图|Figure)?\s*(?:~|\\,|\s)*\\(?:ref|autoref)\{{{re.escape(label)}\}}",
                re.IGNORECASE,
            )
            if any(re.search(INTERPRETIVE_TERMS, context(source, match.start(), match.end())) for match in pattern.finditer(source)):
                discussed.add(label)
        return min(figure_count, len(discussed))

    body_source = source
    if extension == ".md":
        body_source = re.sub(r"!\[[^]]*\]\([^)]*\)", " ", source)
        labels = [str(index) for index in range(1, figure_count + 1)]
    else:
        caption_lines = {re.sub(r"\s+", " ", caption).strip() for caption in captions}
        body_source = "\n".join(
            "" if re.sub(r"\s+", " ", line).strip() in caption_lines else line
            for line in source.splitlines()
        )
        labels = [
            match.group(1)
            for caption in captions
            if (match := re.search(r"图\s*(\d+(?:[-—.]\d+)?)", caption))
        ]
    for label in labels:
        pattern = re.compile(rf"图\s*{re.escape(label)}(?![\d.])")
        if any(re.search(INTERPRETIVE_TERMS, context(body_source, match.start(), match.end())) for match in pattern.finditer(body_source)):
            discussed.add(label)
    return min(figure_count, len(discussed))


def _body_without_bibliography(source: str, extension: str) -> str:
    if extension == ".tex":
        match = re.search(
            r"\\begin\{thebibliography\}|\\bibliography\{|"
            r"\\section\*?\{\s*(?:参考文献|References?)\s*\}",
            source,
            re.IGNORECASE,
        )
    elif extension == ".md":
        match = re.search(r"(?im)^#{1,4}\s*(?:参考文献|References?)\s*$", source)
    else:
        match = re.search(
            r"(?im)^\s*(?:[一二三四五六七八九十0-9]+\s*[、.．]?\s*)?"
            r"(?:参考文献|References?)\s*$",
            source,
        )
    return source[: match.start()] if match else source


def _numeric_validation_signals(plain: str) -> int:
    metric = r"误差|残差|违反量|标准差|方差|置信区间|覆盖率|变化率|偏差|步长|迭代|收敛精度|相对差|绝对差"
    pattern = re.compile(
        rf"(?:{metric})[^。；\n]{{0,36}}(?:为|是|=|:|：|≤|<|达到|降至|不超过)?\s*{NUMERIC_TOKEN}"
        rf"|{NUMERIC_TOKEN}\s*(?:%|s|秒|m|米|次)?[^。；\n]{{0,24}}(?:{metric})",
        re.IGNORECASE,
    )
    cleaned = re.sub(r"(?:图|表|问题|式)\s*\d+(?:[-—.]\d+)?", " ", plain)
    return len(pattern.findall(cleaned))


def _academic_style_findings(plain: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for term, replacement in ACADEMIC_STYLE_TERMS.items():
        count = plain.count(term)
        if count:
            findings.append({"term": term, "count": count, "replacement": replacement})
    return findings


def _metric(name: str, value: Any, target: str) -> dict[str, Any]:
    return {"id": name, "value": value, "target": target}


def _gate(gate_id: str, passed: bool, weight: int, message: str) -> dict[str, Any]:
    return {"id": gate_id, "passed": bool(passed), "weight": weight, "message": message}


def audit(source: str, extension: str, extras: dict[str, int], expected_questions: int, full_paper: bool) -> dict[str, Any]:
    plain = _plain_text(source, extension)
    abstract = _extract_abstract(source)
    abstract_plain = _plain_text(abstract, extension)
    blocks = _section_blocks(source, extension)
    titles = [title for title, _body in blocks]

    detected_questions: dict[int, str] = {}
    question_lengths: dict[int, int] = {}
    question_spans = _question_spans(source, extension)
    for title, body, _start, _end in question_spans:
        index = _question_index(title)
        if index is not None:
            detected_questions[index] = title
            question_lengths[index] = len(_plain_text(body, extension))
    question_count = expected_questions or (max(detected_questions, default=0))
    expected = max(1, question_count)

    figure_count, figure_records = _figure_records(source, extension, extras)
    captions = [str(record["caption"]) for record in figure_records if record.get("caption")]
    table_count = (
        len(re.findall(r"\\begin\{(?:table|longtable)\*?\}", source))
        if extension == ".tex"
        else extras.get("embedded_tables", len(re.findall(r"(?m)^\s*表\s*\d+", source)))
    )
    equation_count = _count_equations(source, extension)
    citation_source = _body_without_bibliography(source, extension)
    if extension == ".tex":
        cited_keys = {
            key.strip()
            for group in re.findall(r"\\cite\w*\{([^}]+)\}", citation_source)
            for key in group.split(",")
            if key.strip()
        }
        citation_count = len(cited_keys)
    else:
        citation_count = len(set(re.findall(r"\[([0-9]{1,2})\]", citation_source)))
    bibliography_count = len(re.findall(r"(?m)\\bibitem\{|^\s*\[[0-9]{1,2}\]", source))
    if extension in {".pdf", ".docx", ".txt"}:
        bibliography_match = re.search(r"参考文献(.*)$", source, re.DOTALL)
        if bibliography_match:
            bibliography_count = max(
                bibliography_count,
                len(re.findall(r"(?m)^\s*(?:\[?\d+\]?|[一二三四五六七八九十]+)[.、 ]", bibliography_match.group(1))),
            )

    numeric_with_unit = len(
        re.findall(
            r"[-+]?\d+(?:\.\d+)?(?:\s*×\s*10\^?[-+]?\d+)?\s*"
            r"(?:%|s|秒|m|米|m/s|km/h|kg|元|万元|℃|°C|度|个|次)(?![A-Za-z])",
            abstract_plain,
            re.IGNORECASE,
        )
    )
    validation_terms = len(
        re.findall(VALIDATION_TERMS, plain)
    )
    validation_numeric_signals = _numeric_validation_signals(plain)
    validation_figures = sum(
        bool(re.search(r"敏感|稳健|鲁棒|收敛|残差|误差|验证|检验|对比|基线|不确定", caption))
        for caption in captions
    )
    figures_by_question = {index: 0 for index in range(1, expected + 1)}
    for record in figure_records:
        caption = str(record.get("caption", ""))
        matched: set[int] = set()
        for token in re.findall(r"(?:问题|Q)\s*([一二三四五六七八九十0-9]+)", caption, re.IGNORECASE):
            index = _question_index(f"问题{token}")
            if index in figures_by_question:
                matched.add(int(index))
        if not matched and isinstance(record.get("start"), int):
            position = int(record["start"])
            for title, _body, start, end in question_spans:
                index = _question_index(title)
                if index in figures_by_question and start <= position < end:
                    matched.add(int(index))
                    break
        for index in matched:
            figures_by_question[index] += 1
    questions_without_figure = [index for index, count in figures_by_question.items() if count == 0]
    dominant_share = max(figures_by_question.values(), default=0) / max(1, figure_count)
    interpretation_count = _count_figure_interpretations(source, extension, captions, figure_count)
    placeholder_count = len(PLACEHOLDER_PATTERN.findall(source))
    style_findings = _academic_style_findings(plain)
    style_finding_count = sum(int(item["count"]) for item in style_findings)
    q_notation_count = _count_q_notation(plain)
    keyword_present = bool(re.search(r"关键词|关键字|Keywords?", source, re.IGNORECASE))
    reference_present = bool(re.search(r"参考文献|thebibliography|References", source, re.IGNORECASE))
    assumption_present = bool(re.search(r"模型假设|基本假设|假设", source))
    symbol_present = bool(re.search(r"符号说明|符号表|主要符号", source))
    conclusion_present = bool(re.search(r"结论|总结", source))
    analysis_present = bool(re.search(r"问题分析|任务分析|模型分析", source))
    pages = extras.get("pages", 0)

    min_figures = max(6, expected + 3) if full_paper else 2
    min_chars = max(8000, expected * 1800) if full_paper else 1500
    min_question_chars = 550 if full_paper else 180
    weak_questions = [
        index for index in range(1, expected + 1) if question_lengths.get(index, 0) < min_question_chars
    ]
    structure_ok = all(
        (bool(abstract_plain), keyword_present, analysis_present, assumption_present, symbol_present, conclusion_present, reference_present)
    )
    depth_ok = len(plain) >= min_chars and not weak_questions and equation_count >= expected + 3
    visual_ok = (
        figure_count >= min_figures
        and validation_figures >= 2
        and interpretation_count >= max(3, expected)
        and not questions_without_figure
        and dominant_share <= 0.40
    )
    validation_ok = (
        validation_terms >= max(8, expected * 2)
        and validation_figures >= 2
        and validation_numeric_signals >= 2
    )
    scholarship_ok = bibliography_count >= 6 and citation_count >= 6
    abstract_ok = bool(abstract_plain) and numeric_with_unit >= expected and 300 <= len(abstract_plain) <= 1400
    language_ok = not full_paper or style_finding_count == 0
    integrity_ok = placeholder_count == 0 and language_ok

    gates = [
        _gate("paper_structure", structure_ok, 16, "摘要、关键词、问题分析、假设、符号、结论和参考文献必须齐全。"),
        _gate("quantitative_abstract", abstract_ok, 14, f"摘要需在合理篇幅内覆盖至少 {expected} 个带单位的量化结果。"),
        _gate("question_depth", depth_ok, 20, f"完整论文需达到证据密度；薄弱分问：{weak_questions or '无'}。"),
        _gate(
            "visual_evidence",
            visual_ok,
            18,
            f"至少需要 {min_figures} 张承担主张的图、每问至少 1 张专属图、至少 2 张检验/对比图，且单问占比不超过 40%；当前无图分问：{questions_without_figure or '无'}。",
        ),
        _gate("validation_traceability", validation_ok, 16, "验证不能集中为一句总评，需有数值检验并由至少两张诊断图支撑。"),
        _gate("scholarly_traceability", scholarship_ok, 10, "至少 6 条参考文献且在正文中实际引用。"),
        _gate(
            "manuscript_integrity",
            integrity_ok,
            6,
            "成稿不得包含 TODO、待补充、占位表达或明显的开发/Agent 质检措辞。",
        ),
    ]
    score = sum(item["weight"] for item in gates if item["passed"])
    issues = [item["message"] for item in gates if not item["passed"]]
    advisories: list[str] = []
    if full_paper and pages and not 18 <= pages <= 28:
        advisories.append(f"当前 {pages} 页；多分问完整国赛论文通常宜在 18–28 页内按证据密度调整，禁止为页数灌水。")
    if figure_count:
        missing_interpretation = max(0, figure_count - interpretation_count)
        if missing_interpretation:
            advisories.append(f"至少 {missing_interpretation} 张图可能缺少正文中的结论性解释。")
    if expected_questions == 0:
        advisories.append("未显式提供 expected_questions；当前按标题自动推断分问数量。")
    if style_findings:
        rendered = "；".join(
            f"{item['term']}×{item['count']}→{item['replacement']}" for item in style_findings
        )
        advisories.append(f"检测到不宜进入竞赛正文的工程化措辞：{rendered}。")
    if full_paper and q_notation_count:
        advisories.append(
            f"正文检测到 {q_notation_count} 处 Q1--Q9 缩写；中文国赛正文宜改为“问题一”--“问题九”，代码或文件名除外。"
        )

    return {
        "passed": all(item["passed"] for item in gates),
        "status": "pass" if all(item["passed"] for item in gates) else "fail",
        "score": score,
        "gates": gates,
        "issues": issues,
        "advisories": advisories,
        "metrics": {
            "characters": len(plain),
            "pages": pages,
            "sections": len(blocks),
            "questions": expected,
            "questionCharacters": {str(key): value for key, value in sorted(question_lengths.items())},
            "abstractCharacters": len(abstract_plain),
            "abstractNumericResults": numeric_with_unit,
            "figures": figure_count,
            "validationFigures": validation_figures,
            "figuresByQuestion": {str(key): value for key, value in figures_by_question.items()},
            "questionsWithoutFigure": questions_without_figure,
            "dominantQuestionFigureShare": dominant_share,
            "tables": table_count,
            "equations": equation_count,
            "citations": citation_count,
            "bibliographyItems": bibliography_count,
            "validationSignals": validation_terms,
            "validationNumericSignals": validation_numeric_signals,
            "figureInterpretations": interpretation_count,
            "placeholders": placeholder_count,
            "academicStyleFindings": style_findings,
            "academicStyleFindingCount": style_finding_count,
            "qNotationCount": q_notation_count,
            "minimumFigures": min_figures,
        },
        "limitations": [
            "该审计检查结构和证据可见性，不验证模型结论是否正确。",
            "通过审计不等于获得任何奖项，也不替代人工逐页复核。",
        ],
    }


def _markdown_report(audit_result: dict[str, Any], source_name: str) -> str:
    metrics = audit_result["metrics"]
    gate_rows = "\n".join(
        f"| {item['id']} | {'PASS' if item['passed'] else 'FAIL'} | {item['message']} |"
        for item in audit_result["gates"]
    )
    issue_lines = "\n".join(f"- {item}" for item in audit_result["issues"]) or "- 无硬门禁问题"
    advisory_lines = "\n".join(f"- {item}" for item in audit_result["advisories"]) or "- 无"
    return f"""# 数学建模竞赛论文成品审计

- 源文件：`{source_name}`
- 源文件 SHA-256：`{metrics.get('artifactSha256', '未绑定')}`
- 完整论文审计：{'是' if metrics.get('fullPaper') else '否'}
- 状态：**{audit_result['status'].upper()}**
- 得分：**{audit_result['score']}/100**
- 正文字符：{metrics['characters']}
- 页数：{metrics['pages'] or '源格式未提供'}
- 分问：{metrics['questions']}
- 图/验证图：{metrics['figures']} / {metrics['validationFigures']}
- 表/公式：{metrics['tables']} / {metrics['equations']}
- 正文引用/文献：{metrics['citations']} / {metrics['bibliographyItems']}
- 工程化措辞命中：{metrics.get('academicStyleFindingCount', 0)}

## 硬门禁

| 门禁 | 结果 | 判据 |
|---|---|---|
{gate_rows}

## 必须修复

{issue_lines}

## 提醒

{advisory_lines}

本报告只审计结构、可见证据与交付完整性；不验证模型正确性，也不构成奖项保证。
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a mathematical-modeling competition manuscript.")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8-sig"))
    input_path = Path(str(spec.get("input_path", ""))).resolve()
    if not input_path.is_file():
        raise ValueError("论文产物不存在")
    source, extras = _read_source(input_path)
    expected_questions = max(0, min(10, int(spec.get("expected_questions", 0))))
    full_paper = bool(spec.get("full_paper", True))
    result = audit(source, input_path.suffix.lower(), extras, expected_questions, full_paper)
    result["metrics"].update(
        {
            "artifactName": input_path.name,
            "artifactSha256": _sha256(input_path),
            "fullPaper": full_paper,
            "expectedQuestions": expected_questions,
        }
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", str(spec.get("filename", "paper-quality-audit"))).strip("-.")
    stem = stem or "paper-quality-audit"
    json_path = args.output_dir / f"{stem}.json"
    md_path = args.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown_report(result, input_path.name), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "audit": result,
                "artifacts": [str(json_path.resolve()), str(md_path.resolve())],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
