from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from pypdf import PdfReader

from scripts.summarize_a_paper_corpus import (
    YEAR_PATTERN,
    extract_text_layer,
    infer_title,
    needs_ocr,
    ocr_pdf,
    public_source_label,
    write_utf8_lf,
)


SECTION_TERMS = {
    "摘要": ("摘要",),
    "关键词": ("关键词", "关键字"),
    "问题重述": ("问题重述", "问题的重述"),
    "问题分析": ("问题分析", "问题的分析"),
    "模型假设": ("模型假设", "模型的假设", "基本假设"),
    "符号说明": ("符号说明", "符号约定", "符号与说明"),
    "模型建立": ("模型建立", "模型的建立", "建立模型"),
    "模型求解": ("模型求解", "模型的求解", "求解模型"),
    "误差或灵敏度": ("误差分析", "灵敏度分析", "敏感性分析", "鲁棒性分析"),
    "模型评价": ("模型评价", "模型的评价", "优缺点", "模型推广"),
    "参考文献": ("参考文献",),
    "附录": ("附录",),
}

WRITING_MARKERS = {
    "逐问映射": ("针对问题一", "针对问题二", "针对问题三", "针对问题1", "针对问题2", "针对问题3"),
    "顺序衔接": ("首先", "其次", "然后", "最后"),
    "因果解释": ("由于", "因此", "从而", "其原因", "这是因为"),
    "图表解读": ("由图", "由表", "从图", "从表", "如图", "如表"),
    "结果落地": ("结果表明", "计算结果", "可知", "可以看出", "说明了"),
    "跨问复用": ("在问题一的基础上", "基于问题一", "基于上述", "进一步地", "进一步考虑"),
    "限制评价": ("模型优点", "模型缺点", "模型不足", "局限性", "模型推广"),
}

CAPTION_PATTERN = re.compile(
    r"(?m)^[ \t]*(?P<kind>图|表)[ \t]*(?P<label>\d+(?:[.．－—_-]\d+)*)"
    r"[ \t：:、.．-]*(?P<title>[^\n]{0,80})"
)
GENERIC_CAPTION = re.compile(r"^(?:结果|流程|示意|曲线|关系|变化|拟合|算法|模型|仿真|比较|对比|分布|结构)(?:图)?$")


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def extract_abstract_length(text: str) -> int | None:
    compact = compact_text(text)
    match = re.search(
        r"摘要(?:[:：])?(.*?)(?:关键词|关键字|一[、.．]问题|1[、.．]问题|问题重述)",
        compact,
        flags=re.DOTALL,
    )
    if not match:
        return None
    body = match.group(1)
    if not 40 <= len(body) <= 2500:
        return None
    return len(body)


def section_hits(text: str) -> list[str]:
    compact = compact_text(text)
    return [name for name, terms in SECTION_TERMS.items() if any(term in compact for term in terms)]


def marker_counts(text: str) -> dict[str, int]:
    compact = compact_text(text)
    return {
        name: sum(compact.count(term) for term in terms)
        for name, terms in WRITING_MARKERS.items()
    }


def caption_inventory(text: str) -> dict[str, object]:
    figures: dict[str, str] = {}
    tables: dict[str, str] = {}
    for match in CAPTION_PATTERN.finditer(text):
        label = match.group("label").replace("．", ".").replace("－", "-").replace("—", "-")
        title = re.sub(r"\s+", " ", match.group("title")).strip(" ：:、.．-")
        target = figures if match.group("kind") == "图" else tables
        if label not in target or len(title) > len(target[label]):
            target[label] = title

    def informative_count(captions: dict[str, str]) -> int:
        return sum(
            1
            for title in captions.values()
            if len(compact_text(title)) >= 5 and not GENERIC_CAPTION.fullmatch(compact_text(title))
        )

    return {
        "figureCaptions": len(figures),
        "tableCaptions": len(tables),
        "informativeFigureCaptions": informative_count(figures),
        "informativeTableCaptions": informative_count(tables),
    }


def count_image_objects(reader: PdfReader) -> tuple[int, int]:
    image_count = 0
    pages_with_images = 0
    for page in reader.pages:
        page_images = 0
        try:
            resources = page.get("/Resources")
            resources = resources.get_object() if resources else None
            xobjects = resources.get("/XObject") if resources else None
            xobjects = xobjects.get_object() if xobjects else None
            if xobjects:
                for item in xobjects.values():
                    obj = item.get_object()
                    if obj.get("/Subtype") == "/Image":
                        page_images += 1
        except (AttributeError, KeyError, TypeError, ValueError):
            page_images = 0
        image_count += page_images
        pages_with_images += int(page_images > 0)
    return image_count, pages_with_images


def analyze_pdf(path: Path, root: Path, ocr_mode: str, ocr_cache: Path) -> dict[str, object]:
    pages, page_count = extract_text_layer(path)
    extraction = "text-layer"
    if needs_ocr(pages) and ocr_mode != "none":
        ocr_pages = ocr_pdf(path, page_count, ocr_cache, ocr_mode)
        if sum(len(page) for page in ocr_pages) >= 500:
            pages = ocr_pages
            extraction = f"ocr-{ocr_mode}"
    text = "\n".join(page for page in pages if page)
    reader = PdfReader(str(path), strict=False)
    image_objects, pages_with_images = count_image_objects(reader)
    relative = path.relative_to(root).as_posix()
    year_match = YEAR_PATTERN.search(relative)
    captions = caption_inventory(text)
    return {
        "year": int(year_match.group()) if year_match else None,
        "title": infer_title(path, pages[0] if pages else ""),
        "source": public_source_label(path, root),
        "pages": page_count,
        "extraction": extraction if text else "empty",
        "abstractCharacters": extract_abstract_length("\n".join(pages[:3])),
        "sections": section_hits(text),
        "writingMarkers": marker_counts(text),
        **captions,
        "imageObjects": image_objects,
        "pagesWithImages": pages_with_images,
        "visualMetricBoundary": "imageObjects excludes vector drawings and may count a scanned page as one image",
    }


def render_markdown(records: list[dict[str, object]]) -> str:
    section_coverage: Counter[str] = Counter()
    marker_totals: Counter[str] = Counter()
    year_stats: dict[int, dict[str, object]] = defaultdict(
        lambda: {"papers": 0, "pages": 0, "abstracts": [], "figures": 0, "tables": 0}
    )
    for record in records:
        section_coverage.update(record["sections"])
        marker_totals.update(record["writingMarkers"])
        year = record["year"]
        if year is None:
            continue
        stats = year_stats[year]
        stats["papers"] += 1
        stats["pages"] += record["pages"]
        stats["figures"] += record["figureCaptions"]
        stats["tables"] += record["tableCaptions"]
        if record["abstractCharacters"] is not None:
            stats["abstracts"].append(record["abstractCharacters"])

    abstract_lengths = [record["abstractCharacters"] for record in records if record["abstractCharacters"] is not None]
    lines = [
        "# 2009-2023 国赛 A 题优秀论文呈现方式索引",
        "",
        "> 本索引对章节、摘要、题注和行文标记作确定性扫描，用于发现需要回读的论文；审美与论证质量仍须查看原 PDF 页面，不得仅凭计数下结论。",
        "",
        f"覆盖 {len(records)} 份 PDF。成功识别 {len(abstract_lengths)} 份摘要长度；中位数为 {int(median(abstract_lengths)) if abstract_lengths else '未识别'} 字符。",
        "",
        "## 年份级概览",
        "",
        "| 年份 | 论文数 | 总页数 | 可识别摘要中位字符数 | 图题数 | 表题数 |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for year in sorted(year_stats):
        stats = year_stats[year]
        abstract_median = int(median(stats["abstracts"])) if stats["abstracts"] else "—"
        lines.append(
            f"| {year} | {stats['papers']} | {stats['pages']} | {abstract_median} | {stats['figures']} | {stats['tables']} |"
        )

    lines.extend(["", "## 章节覆盖", ""])
    lines.extend(f"- {name}: {section_coverage[name]}/{len(records)} 篇命中" for name in SECTION_TERMS)
    lines.extend(["", "## 行文信号总命中次数", ""])
    lines.extend(f"- {name}: {marker_totals[name]} 次" for name in WRITING_MARKERS)
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 图题与表题依赖文本行结构；OCR、双栏读取顺序和拆字可能漏计，必须回看原页。",
            "- PDF 图像对象不等于论文插图：矢量图可能计为 0，扫描页可能整页计为 1，因此只用于选择视觉抽样页。",
            "- 词频不是写作质量。Agent 应学习章节功能、主张—证据关系和图文闭环，而非机械增加“首先”“可知”等套话。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze presentation patterns in CUMCM A-paper PDFs.")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", required=True, type=Path)
    parser.add_argument("--ocr", choices=("none", "representative", "full"), default="none")
    parser.add_argument("--ocr-cache", type=Path, default=Path(".agent-data/a-paper-ocr"))
    args = parser.parse_args()

    root = args.corpus.expanduser().resolve()
    pdfs = sorted(root.rglob("*.pdf"), key=lambda path: str(path).casefold())
    records = []
    for index, path in enumerate(pdfs, start=1):
        print(f"[{index}/{len(pdfs)}] {path.name}", flush=True)
        records.append(analyze_pdf(path, root, args.ocr, args.ocr_cache.resolve()))
    records.sort(key=lambda record: (record["year"] or 0, str(record["source"]).casefold()))

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(args.json_output, json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    write_utf8_lf(args.markdown_output, render_markdown(records))
    print(f"Wrote {len(records)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
