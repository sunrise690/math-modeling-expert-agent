from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

import numpy as np
from PIL import Image

from scripts.analyze_a_paper_presentation import (
    CAPTION_PATTERN,
    SECTION_TERMS,
    caption_inventory,
    extract_abstract_length,
    marker_counts,
    section_hits,
)
from scripts.summarize_a_paper_corpus import (
    extract_text_layer,
    file_sha256,
    find_native_command,
    needs_ocr,
    normalize_text,
    ocr_pdf,
    term_hits,
    term_pages,
    write_utf8_lf,
)


EDITION_NUMBERS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
EDITION_PATTERN = re.compile(r"第([一二三四五六七八九十]|\d+)届")
PROBLEM_PATTERN = re.compile(r"([ABC])题", re.IGNORECASE)
PAPER_NUMBER_PATTERN = re.compile(r"优秀论文[-_ ]?(\d+)", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"20\d{2}")

TITLE_HINT = re.compile(
    r"基于|模型|优化|设计|研究|分析|规划|控制|预测|性能|影响|应用|方案|方法|系统"
)
TITLE_NOISE = re.compile(
    r"所属类别|参赛编号|本科组|研究生组|华数杯|数学建模竞赛|摘要|关键词|关键字|承诺书|^\d+$|CM\d+"
)

METHOD_TERMS = {
    "传热与多物理机理": (
        "热传导方程",
        "有限差分",
        "牛顿冷却",
        "动力学模型",
        "状态方程",
        "布朗扩散",
        "Smoluchowski",
        "Kubelka-Munk",
    ),
    "光学、光谱与色度": (
        "反射率",
        "光谱功率分布",
        "CIE 1931",
        "TM-30",
        "mel-DER",
        "三刺激值",
        "Kubelka-Munk",
        "色差",
    ),
    "机器人、几何与坐标": (
        "D-H",
        "运动学方程",
        "坐标转换",
        "空间直角坐标",
        "欧氏距离",
        "栅格图",
        "机械臂",
    ),
    "图论与路径规划": (
        "最短路径",
        "Dijkstra",
        "A*算法",
        "A∗算法",
        "蚁群算法",
        "旅行商",
        "路径规划",
    ),
    "多指标综合评价": (
        "TOPSIS",
        "Topsis",
        "熵权法",
        "主成分分析",
        "灰色关联",
        "层次分析",
        "综合评价",
    ),
    "统计推断与回归": (
        "卡方检验",
        "Spearman",
        "斯皮尔曼",
        "方差分析",
        "Friedman",
        "Wilcoxon",
        "效应量",
        "逻辑回归",
        "相关系数",
    ),
    "机器学习": (
        "随机森林",
        "XGBoost",
        "XGboost",
        "梯度提升树",
        "支持向量机",
        "神经网络",
        "K-means",
    ),
    "连续、整数与多目标规划": (
        "线性规划",
        "整数规划",
        "非线性规划",
        "多目标优化",
        "目标规划",
        "0-1规划",
        "分层序列",
        "Minimize",
    ),
    "随机与群智能优化": (
        "模拟退火",
        "差分进化",
        "粒子群",
        "蚁群算法",
        "遗传算法",
        "蒙特卡洛",
        "随机重启",
    ),
    "仿真、调度与资源分配": (
        "动态调度",
        "离散事件",
        "资源分配",
        "网络切片",
        "蒙特卡洛模拟",
        "动态规划模型",
    ),
}

VALIDATION_TERMS = {
    "误差、残差或实测对照": (
        "误差分析",
        "相对误差",
        "绝对误差",
        "残差",
        "均方根误差",
        "RMSE",
        "决定系数",
        "R²",
        "拟合优度",
    ),
    "样本外或交叉验证": (
        "交叉验证",
        "训练集",
        "测试集",
        "验证集",
        "留出",
        "混淆矩阵",
    ),
    "数值或算法收敛": (
        "收敛分析",
        "收敛曲线",
        "步长",
        "网格",
        "迭代次数",
        "终止条件",
    ),
    "灵敏度与鲁棒性": (
        "灵敏度分析",
        "敏感性分析",
        "鲁棒性",
        "稳健性",
        "扰动",
    ),
    "随机重复": (
        "随机种子",
        "多次运行",
        "重复实验",
        "随机重启",
        "均值和方差",
        "置信区间",
    ),
    "统计显著性与效应量": (
        "p 值",
        "P 值",
        "显著性",
        "效应量",
        "置信区间",
        "Bonferroni",
    ),
    "约束或可行性复核": (
        "约束检验",
        "可行性检验",
        "约束条件",
        "约束违反",
        "模型检验",
    ),
}

HUE_BINS = (
    ("红", 0.0, 15.0),
    ("橙", 15.0, 45.0),
    ("黄", 45.0, 70.0),
    ("绿", 70.0, 165.0),
    ("青", 165.0, 195.0),
    ("蓝", 195.0, 255.0),
    ("紫", 255.0, 290.0),
    ("品红", 290.0, 345.0),
    ("红", 345.0, 360.0),
)


def parse_identity(path: Path, root: Path) -> dict[str, object]:
    relative = path.relative_to(root).as_posix()
    edition_match = EDITION_PATTERN.search(relative)
    edition_token = edition_match.group(1) if edition_match else ""
    edition = int(edition_token) if edition_token.isdigit() else EDITION_NUMBERS.get(edition_token)
    problem_match = PROBLEM_PATTERN.search(path.name)
    paper_match = PAPER_NUMBER_PATTERN.search(path.stem)
    problem = problem_match.group(1).upper() if problem_match else None
    paper_number = int(paper_match.group(1)) if paper_match else None
    return {
        "edition": edition,
        "editionLabel": f"第{edition_token}届" if edition_token else "未识别届次",
        "problem": problem,
        "paperNumber": paper_number,
    }


def clean_title_line(raw: str) -> str:
    return utf8_safe(re.sub(r"\s+", " ", raw).strip(" \t-—_：:，,。·"))


def utf8_safe(value: str) -> str:
    return value.encode("utf-8", errors="replace").decode("utf-8")


def sanitize_strings(value: object) -> object:
    if isinstance(value, str):
        return utf8_safe(value)
    if isinstance(value, list):
        return [sanitize_strings(item) for item in value]
    if isinstance(value, dict):
        return {utf8_safe(str(key)): sanitize_strings(item) for key, item in value.items()}
    return value


def infer_title(pages: list[str], fallback: str) -> str:
    candidates: list[tuple[int, int, str]] = []
    for page_index, page in enumerate(pages[:3]):
        prefix = re.split(r"摘要|摘 要", page, maxsplit=1)[0]
        lines = [clean_title_line(line) for line in prefix.splitlines()]
        for line_index, line in enumerate(lines[:60]):
            compact = re.sub(r"\s+", "", line)
            if not 6 <= len(compact) <= 55 or TITLE_NOISE.search(compact):
                continue
            cjk = len(re.findall(r"[\u3400-\u9fff]", compact))
            if cjk < 5:
                continue
            score = 0
            score += 7 if TITLE_HINT.search(compact) else 0
            score += 4 if page_index == 0 else 0
            score += 2 if 10 <= len(compact) <= 32 else 0
            score += 2 if line_index >= 2 else 0
            score -= 5 if compact.startswith(("本文", "针对", "对于", "首先", "近年来")) else 0
            score -= 4 if any(mark in compact for mark in ("。", "；", ";")) else 0
            candidates.append((score, -line_index, line))
    if candidates:
        return max(candidates)[2]
    return fallback


def section_page_map(pages: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for page_number, page in enumerate(pages, start=1):
        compact = re.sub(r"\s+", "", page)
        for name, terms in SECTION_TERMS.items():
            if name not in result and any(term in compact for term in terms):
                result[name] = page_number
    return result


def terminal_section_start(pages: list[str]) -> int | None:
    patterns = (
        re.compile(r"^\s*(?:\d+(?:[.．]\d+)*)?\s*参考文献\s*$"),
        re.compile(r"^\s*(?:\d+(?:[.．]\d+)*)?\s*附录(?:\s*[A-Z一二三四五六])?\s*$"),
    )
    minimum_page = max(4, round(len(pages) * 0.35))
    candidates: list[int] = []
    for page_number, page in enumerate(pages, start=1):
        if page_number < minimum_page:
            continue
        lines = [clean_title_line(line) for line in page.splitlines()]
        if any(pattern.fullmatch(line) for line in lines for pattern in patterns):
            candidates.append(page_number)
    return min(candidates) if candidates else None


def caption_records(pages: list[str]) -> list[dict[str, object]]:
    seen: set[tuple[str, str]] = set()
    records: list[dict[str, object]] = []
    for page_number, page in enumerate(pages, start=1):
        for match in CAPTION_PATTERN.finditer(page):
            kind = match.group("kind")
            label = match.group("label").replace("．", ".").replace("－", "-").replace("—", "-")
            key = (kind, label)
            if key in seen:
                continue
            seen.add(key)
            title = clean_title_line(match.group("title"))[:80]
            records.append({"kind": kind, "label": label, "title": title, "page": page_number})
    return records


def hue_names(hue_degrees: np.ndarray) -> Counter[str]:
    counts: Counter[str] = Counter()
    for name, start, end in HUE_BINS:
        counts[name] += int(np.count_nonzero((hue_degrees >= start) & (hue_degrees < end)))
    return counts


def analyze_image_color(path: Path) -> dict[str, object]:
    with Image.open(path) as image:
        image = image.convert("RGB")
        if image.width > 360:
            height = max(1, round(image.height * 360 / image.width))
            image = image.resize((360, height), Image.Resampling.BILINEAR)
        rgb = np.asarray(image, dtype=np.uint8)
    flat = rgb.reshape(-1, 3).astype(np.float32)
    maximum = flat.max(axis=1)
    minimum = flat.min(axis=1)
    delta = maximum - minimum
    saturation = delta / np.maximum(maximum, 1.0)
    colored = (saturation >= 0.16) & (delta >= 22.0) & (maximum >= 45.0) & (maximum <= 250.0)
    colored_pixels = flat[colored]
    if not len(colored_pixels):
        return {
            "chromaticRatio": 0.0,
            "chromaticPixels": 0,
            "hueCounts": {},
            "quantizedRgbCounts": {},
        }

    cmax = colored_pixels.max(axis=1)
    cmin = colored_pixels.min(axis=1)
    cdelta = np.maximum(cmax - cmin, 1.0)
    hue = np.zeros(len(colored_pixels), dtype=np.float32)
    red_max = colored_pixels[:, 0] == cmax
    green_max = (~red_max) & (colored_pixels[:, 1] == cmax)
    blue_max = ~(red_max | green_max)
    hue[red_max] = ((colored_pixels[red_max, 1] - colored_pixels[red_max, 2]) / cdelta[red_max]) % 6
    hue[green_max] = (colored_pixels[green_max, 2] - colored_pixels[green_max, 0]) / cdelta[green_max] + 2
    hue[blue_max] = (colored_pixels[blue_max, 0] - colored_pixels[blue_max, 1]) / cdelta[blue_max] + 4
    hue *= 60.0

    quantized = (colored_pixels.astype(np.uint16) // 32 * 32).astype(np.uint8)
    rgb_counts: Counter[str] = Counter(
        f"#{red:02X}{green:02X}{blue:02X}" for red, green, blue in quantized.tolist()
    )
    return {
        "chromaticRatio": round(len(colored_pixels) / len(flat), 6),
        "chromaticPixels": int(len(colored_pixels)),
        "hueCounts": dict(hue_names(hue)),
        "quantizedRgbCounts": dict(rgb_counts),
    }


def render_and_profile(
    path: Path,
    page_count: int,
    eligible_pages: set[int],
    preferred_pages: set[int],
    review_dir: Path | None,
    paper_id: str,
) -> dict[str, object]:
    pdftoppm = find_native_command("pdftoppm")
    if not pdftoppm:
        return {"status": "unavailable", "reason": "pdftoppm not found"}
    hue_totals: Counter[str] = Counter()
    rgb_totals: Counter[str] = Counter()
    chromatic_pixels = 0
    page_metrics: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="huashu-visual-") as temp_dir:
        prefix = Path(temp_dir) / "page"
        render = subprocess.run(
            [pdftoppm, "-png", "-r", "72", str(path), str(prefix)],
            capture_output=True,
            check=False,
        )
        if render.returncode != 0:
            return {
                "status": "failed",
                "reason": render.stderr.decode("utf-8", errors="replace").strip(),
            }
        for image_path in sorted(Path(temp_dir).glob("page-*.png")):
            match = re.search(r"-(\d+)\.png$", image_path.name)
            if not match:
                continue
            page_number = int(match.group(1))
            metrics = analyze_image_color(image_path)
            if page_number in eligible_pages:
                hue_totals.update(metrics["hueCounts"])
                rgb_totals.update(metrics["quantizedRgbCounts"])
                chromatic_pixels += int(metrics["chromaticPixels"])
                page_metrics.append(
                    {
                        "page": page_number,
                        "chromaticRatio": metrics["chromaticRatio"],
                        "preferred": page_number in preferred_pages,
                        "path": image_path,
                    }
                )

        page_metrics.sort(
            key=lambda item: (
                -float(item["chromaticRatio"]),
                -int(bool(item["preferred"])),
                int(item["page"]),
            )
        )
        if page_metrics and float(page_metrics[0]["chromaticRatio"]) < 0.001:
            preferred = [item for item in page_metrics if item["preferred"]]
            if preferred:
                page_metrics = preferred + [item for item in page_metrics if not item["preferred"]]
        top_pages = page_metrics[:3]
        review_files: list[str] = []
        if review_dir and top_pages:
            review_dir.mkdir(parents=True, exist_ok=True)
            for rank, item in enumerate(top_pages, start=1):
                destination = review_dir / f"{paper_id}-rank{rank}-p{item['page']}.png"
                shutil.copyfile(item["path"], destination)
                review_files.append(destination.name)

    total_hues = sum(hue_totals.values())
    color_signal_available = chromatic_pixels >= 100
    dominant_hues = [
        {"name": name, "share": round(count / total_hues, 4)}
        for name, count in hue_totals.most_common(4)
        if total_hues and count > 0
    ] if color_signal_available else []
    total_rgb = sum(rgb_totals.values())
    dominant_rgb = [
        {"hex": color, "share": round(count / total_rgb, 4)}
        for color, count in rgb_totals.most_common(8)
        if total_rgb and count > 0
    ] if color_signal_available else []
    return {
        "status": "ok",
        "eligiblePageCount": len(eligible_pages),
        "chromaticPixels": chromatic_pixels,
        "chromaticPageCount": sum(float(item["chromaticRatio"]) >= 0.001 for item in page_metrics),
        "dominantHues": dominant_hues,
        "dominantQuantizedRgb": dominant_rgb,
        "topColorPages": [
            {"page": int(item["page"]), "chromaticRatio": item["chromaticRatio"]} for item in top_pages
        ],
        "reviewFiles": review_files,
        "metricBoundary": (
            "低分辨率栅格像素统计仅用于定位彩色页面；照片、地图、校徽和抗锯齿均可能影响占比，"
            "配色质量必须回看原页。"
        ),
    }


def summarize_pdf(
    path: Path,
    root: Path,
    ocr_mode: str,
    ocr_cache: Path,
    review_dir: Path | None,
    render_visuals: bool,
) -> dict[str, object]:
    identity = parse_identity(path, root)
    pages, page_count = extract_text_layer(path)
    extraction = "text-layer"
    if needs_ocr(pages) and ocr_mode != "none":
        ocr_pages = ocr_pdf(path, page_count, ocr_cache, ocr_mode)
        if sum(len(page) for page in ocr_pages) >= 500:
            pages = ocr_pages
            extraction = f"ocr-{ocr_mode}"
    text = "\n".join(page for page in pages if page)
    first_pages = "\n".join(pages[:3])
    year_match = YEAR_PATTERN.search(first_pages)
    year = int(year_match.group()) if year_match else None
    digest = file_sha256(path)
    paper_id = (
        f"huashu-{year or 'unknown'}-{identity['problem'] or 'unknown'}-"
        f"{identity['paperNumber'] or 'unknown'}-{digest[:8]}"
    )
    captions = caption_records(pages)
    caption_summary = caption_inventory(text)
    section_pages = section_page_map(pages)
    terminal_start = terminal_section_start(pages)
    main_body_end = terminal_start - 1 if terminal_start else page_count
    caption_pages = {int(record["page"]) for record in captions if record["kind"] == "图"}
    body_pages = set(range(2, max(2, main_body_end) + 1))
    eligible_pages = body_pages
    preferred_pages = caption_pages & body_pages
    inferred_title = infer_title(pages, path.stem)
    title_evidence = "pdf-text-layer"
    if (
        inferred_title == path.stem
        and identity["edition"] == 5
        and identity["problem"] == "C"
        and identity["paperNumber"] == 1
    ):
        inferred_title = "游客在华旅游规划（原题名因 PDF 字体缺失未恢复）"
        title_evidence = "由问题链、地图页和可识别术语概括；不是原题名转录"
    visual = (
        render_and_profile(path, page_count, eligible_pages, preferred_pages, review_dir, paper_id)
        if render_visuals
        else {"status": "not-run"}
    )
    return {
        "paperId": paper_id,
        **identity,
        "year": year,
        "title": inferred_title,
        "titleEvidence": title_evidence,
        "source": f"{identity['editionLabel']}/{identity['problem'] or '?'}{identity['paperNumber'] or '?'}"
        f"/paper-{digest[:12]}.pdf",
        "sha256": digest,
        "pages": page_count,
        "characters": len(text),
        "extraction": extraction if text else "empty",
        "methodFamilies": term_hits(text, METHOD_TERMS),
        "methodPages": term_pages(pages, METHOD_TERMS),
        "validationSignals": term_hits(text, VALIDATION_TERMS),
        "validationPages": term_pages(pages, VALIDATION_TERMS),
        "abstractCharacters": extract_abstract_length(first_pages),
        "sections": section_hits(text),
        "sectionPages": section_pages,
        "writingMarkers": marker_counts(text),
        **caption_summary,
        "captionSamples": captions[:80],
        "mainBodyEndPage": main_body_end,
        "visualProfile": visual,
    }


def aggregate(records: list[dict[str, object]]) -> dict[str, object]:
    method_counts: Counter[str] = Counter()
    validation_counts: Counter[str] = Counter()
    section_counts: Counter[str] = Counter()
    marker_totals: Counter[str] = Counter()
    hue_totals: Counter[str] = Counter()
    for record in records:
        method_counts.update(record["methodFamilies"].keys())
        validation_counts.update(record["validationSignals"].keys())
        section_counts.update(record["sections"])
        marker_totals.update(record["writingMarkers"])
        for item in record["visualProfile"].get("dominantHues", []):
            hue_totals[item["name"]] += round(float(item["share"]) * 10_000)
    abstract_lengths = [
        int(record["abstractCharacters"])
        for record in records
        if record["abstractCharacters"] is not None
    ]
    return {
        "paperCount": len(records),
        "pageCount": sum(int(record["pages"]) for record in records),
        "editions": sorted({int(record["edition"]) for record in records if record["edition"] is not None}),
        "years": sorted({int(record["year"]) for record in records if record["year"] is not None}),
        "methodCoverage": dict(method_counts.most_common()),
        "validationCoverage": dict(validation_counts.most_common()),
        "sectionCoverage": {name: section_counts[name] for name in SECTION_TERMS},
        "writingMarkerTotals": dict(marker_totals),
        "figureCaptions": sum(int(record["figureCaptions"]) for record in records),
        "tableCaptions": sum(int(record["tableCaptions"]) for record in records),
        "abstractMedianCharacters": int(median(abstract_lengths)) if abstract_lengths else None,
        "dominantHueRoutingSignal": [name for name, _ in hue_totals.most_common()],
    }


def render_markdown(records: list[dict[str, object]], summary: dict[str, object]) -> str:
    lines = [
        "# 华数杯第四至第六届优秀论文语料索引",
        "",
        "> 本索引由 PDF 文本层、必要 OCR、题注扫描和低分辨率像素统计生成，只用于检索路由。"
        "模型是否为主模型、验证是否充分、图表是否美观，必须回到原 PDF 对应页核验。",
        "",
        f"覆盖 {summary['paperCount']} 份 PDF、{summary['pageCount']} 个物理页；"
        f"届次为 {summary['editions']}，可识别年份为 {summary['years']}。",
        "",
        "## 逐篇索引",
        "",
        "| 届次 | 年份 | 题目 | 论文 | 页数 | 文本来源 | 方法族 | 验证信号 | 图/表题 | 主色路由信号 |",
        "|---:|---:|:---:|---|---:|---|---|---|---:|---|",
    ]
    for record in sorted(
        records,
        key=lambda item: (
            int(item["edition"] or 0),
            str(item["problem"] or ""),
            int(item["paperNumber"] or 0),
        ),
    ):
        methods = "、".join(record["methodFamilies"].keys()) or "未自动识别"
        validations = "、".join(record["validationSignals"].keys()) or "未自动识别"
        hue_signal = "、".join(item["name"] for item in record["visualProfile"].get("dominantHues", [])[:3])
        title = str(record["title"]).replace("|", "\\|")
        lines.append(
            f"| {record['editionLabel']} | {record['year'] or '—'} | {record['problem'] or '—'} | {title} | "
            f"{record['pages']} | {record['extraction']} | {methods} | {validations} | "
            f"{record['figureCaptions']}/{record['tableCaptions']} | {hue_signal or '近单色'} |"
        )

    lines.extend(["", "## 方法族覆盖", ""])
    lines.extend(f"- {name}: {count}/{summary['paperCount']} 篇命中" for name, count in summary["methodCoverage"].items())
    lines.extend(["", "## 验证信号覆盖", ""])
    lines.extend(
        f"- {name}: {count}/{summary['paperCount']} 篇命中"
        for name, count in summary["validationCoverage"].items()
    )
    lines.extend(
        [
            "",
            "## 呈现方式概览",
            "",
            f"- 共识别图题 {summary['figureCaptions']} 个、表题 {summary['tableCaptions']} 个。",
            f"- 可识别摘要的中位长度为 {summary['abstractMedianCharacters'] or '—'} 字符；该值是历史描述，不是篇幅目标。",
        ]
    )
    lines.extend(
        f"- {name}: {summary['sectionCoverage'][name]}/{summary['paperCount']} 篇命中"
        for name in SECTION_TERMS
    )
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 文件名中的“优秀论文”来自资料包，未逐篇核验具体奖项等级。",
            "- 关键词出现不等于方法被正确使用；必须回读模型定义、结果和验证页。",
            "- 图题正则可能受双栏、公式字体和 OCR 拆字影响；计数用于选页，不用于评价质量。",
            "- 色相统计会受照片、地图、校徽、抗锯齿和扫描底色影响；配色结论必须查看代表页。",
            "- 只迁移问题结构、论证组织与可验证视觉编码，不复制论文原句、结论数值或旧式模板。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Huashu Cup excellent-paper corpora.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", required=True, type=Path)
    parser.add_argument("--ocr", choices=("none", "representative", "full"), default="representative")
    parser.add_argument("--ocr-cache", type=Path, default=Path(".agent-data/huashu-cup-ocr"))
    parser.add_argument("--render-visuals", action="store_true")
    parser.add_argument("--review-dir", type=Path)
    args = parser.parse_args()

    root = args.corpus.expanduser().resolve()
    pdfs = sorted(root.rglob("*.pdf"), key=lambda path: str(path).casefold())
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found under {root}")
    review_dir = args.review_dir.resolve() if args.review_dir else None
    records = []
    for index, path in enumerate(pdfs, start=1):
        print(f"[{index}/{len(pdfs)}] {path.parent.name}/{path.name}", flush=True)
        records.append(
            summarize_pdf(
                path,
                root,
                args.ocr,
                args.ocr_cache.resolve(),
                review_dir,
                args.render_visuals,
            )
        )
    edition_years: dict[int, Counter[int]] = defaultdict(Counter)
    for record in records:
        if record["edition"] is not None and record["year"] is not None:
            edition_years[int(record["edition"])][int(record["year"])] += 1
    for record in records:
        if record["year"] is None and record["edition"] in edition_years:
            record["year"] = edition_years[int(record["edition"])].most_common(1)[0][0]
            record["yearInference"] = "同届其他论文首页年份的多数值"
            record["paperId"] = re.sub(r"huashu-unknown-", f"huashu-{record['year']}-", record["paperId"])
    summary = aggregate(records)
    serializable_records = sanitize_strings(records)
    for record in serializable_records:
        record["visualProfile"].pop("reviewFiles", None)
    payload = {
        "schemaVersion": 1,
        "collection": "华数杯全国大学生数学建模竞赛第四至第六届优秀论文",
        "boundary": "Derived routing index; inspect source PDF pages before making content or quality claims.",
        "summary": summary,
        "papers": serializable_records,
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(args.json_output, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    write_utf8_lf(args.markdown_output, render_markdown(records, summary))
    if review_dir:
        review_manifest = {
            "collectionSha256": hashlib.sha256(
                "".join(record["sha256"] for record in records).encode("ascii")
            ).hexdigest(),
            "papers": [
                {
                    "paperId": record["paperId"],
                    "title": record["title"],
                    "topColorPages": record["visualProfile"].get("topColorPages", []),
                    "reviewFiles": record["visualProfile"].get("reviewFiles", []),
                }
                for record in records
            ],
        }
        write_utf8_lf(review_dir / "review-manifest.json", json.dumps(review_manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {len(records)} records and {summary['pageCount']} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
