from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


METHOD_TERMS = {
    "机理与守恒": ("动力学", "微分方程", "热传导", "能量守恒", "质量守恒", "受力分析", "力矩", "状态方程"),
    "几何与坐标": ("空间直角坐标", "坐标变换", "几何模型", "轨迹", "太阳高度角", "方位角", "投影"),
    "数值计算": ("有限差分", "龙格库塔", "欧拉法", "数值积分", "二分法", "牛顿迭代", "差分方程"),
    "拟合与估计": ("最小二乘", "曲线拟合", "回归分析", "参数估计", "参数辨识", "插值", "相关系数"),
    "统计与评价": ("主成分分析", "聚类分析", "灰色关联", "模糊综合评价", "层次分析", "熵权", "假设检验"),
    "规划与确定性优化": ("线性规划", "非线性规划", "整数规划", "0-1规划", "多目标优化", "动态规划", "穷举", "网格搜索"),
    "随机与启发式优化": ("遗传算法", "粒子群", "模拟退火", "蚁群算法", "蒙特卡洛", "随机搜索"),
    "仿真与调度": ("元胞自动机", "离散事件", "排队模型", "动态调度", "计算机仿真", "数值模拟"),
}

VALIDATION_TERMS = {
    "误差或实测对照": ("误差分析", "相对误差", "绝对误差", "实测", "对比分析", "拟合优度", "决定系数"),
    "灵敏度": ("灵敏度分析", "敏感性分析"),
    "鲁棒性": ("鲁棒性", "稳健性"),
    "数值收敛": ("步长", "网格", "收敛性", "收敛分析", "稳定性条件"),
    "独立检验": ("模型检验", "交叉验证", "残差分析", "置信区间", "显著性检验", "独立验证"),
    "随机重复": ("多次运行", "重复实验", "随机种子", "均值和方差", "置信水平"),
}

GENERIC_STEM = re.compile(r"^(?:A[-_]?\d+.*|\d+|\d{4}国赛(?:国家)?一等奖A题优秀论文\d*)$", re.IGNORECASE)
TITLE_HINT = re.compile(r"研究|设计|控制|分析|优化|模型|定位|系统|问题|功率|标定|重建|成像|求解")
YEAR_PATTERN = re.compile(r"20(?:0\d|1\d|2\d)")
TITLE_NOISE = re.compile(r"承诺|咨询|讨论|指导教师|参赛队|答卷|编号|赛区|评阅|值得研究的方向")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def find_native_command(name: str) -> str | None:
    executable_suffixes = {".exe", ""} if os.name == "nt" else {""}
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        for suffix in executable_suffixes:
            candidate = Path(directory) / f"{name}{suffix}"
            if candidate.is_file():
                return str(candidate)
    return shutil.which(name)


def extract_text_layer(path: Path) -> tuple[list[str], int]:
    reader = PdfReader(str(path), strict=False)
    pages = [normalize_text(page.extract_text() or "") for page in reader.pages]
    return pages, len(reader.pages)


def ocr_pdf(path: Path, page_count: int, cache_dir: Path, mode: str) -> list[str]:
    digest = file_sha256(path)
    cache_path = cache_dir / f"{digest}-{mode}.json"
    if cache_path.is_file():
        cached_pages = json.loads(cache_path.read_text(encoding="utf-8"))["pages"]
        if sum(len(page) for page in cached_pages) >= 500:
            return cached_pages
    pdftoppm = find_native_command("pdftoppm")
    tesseract = find_native_command("tesseract")
    if not pdftoppm or not tesseract:
        return []
    if mode == "full":
        selected = list(range(1, page_count + 1))
    elif page_count <= 40:
        selected = list(range(1, page_count + 1))
    else:
        selected = sorted(set(range(1, min(page_count, 20) + 1)) | set(range(max(1, page_count - 9), page_count + 1)))
    pages = [""] * page_count
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="a-paper-ocr-") as temp_dir:
        temp_root = Path(temp_dir)
        for page_number in selected:
            prefix = temp_root / f"page-{page_number:04d}"
            render = subprocess.run(
                [
                    pdftoppm,
                    "-f",
                    str(page_number),
                    "-l",
                    str(page_number),
                    "-r",
                    "150",
                    "-singlefile",
                    "-png",
                    str(path),
                    str(prefix),
                ],
                capture_output=True,
                check=False,
            )
            image_path = prefix.with_suffix(".png")
            if render.returncode != 0 or not image_path.is_file():
                continue
            ocr = subprocess.run(
                [tesseract, str(image_path), "stdout", "-l", "chi_sim+eng", "--psm", "6"],
                capture_output=True,
                check=False,
            )
            if ocr.returncode == 0:
                pages[page_number - 1] = normalize_text(ocr.stdout.decode("utf-8", errors="replace"))
    cache_path.write_text(
        json.dumps({"sourceSha256": digest, "mode": mode, "pages": pages}, ensure_ascii=False),
        encoding="utf-8",
    )
    return pages


def term_hits(text: str, taxonomy: dict[str, tuple[str, ...]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    folded = text.casefold()
    for family, terms in taxonomy.items():
        present = [term for term in terms if term.casefold() in folded]
        if present:
            result[family] = present
    return result


def term_pages(pages: list[str], taxonomy: dict[str, tuple[str, ...]]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for family, terms in taxonomy.items():
        hits = []
        folded_terms = [term.casefold() for term in terms]
        for page_number, page in enumerate(pages, start=1):
            folded_page = page.casefold()
            if any(term in folded_page for term in folded_terms):
                hits.append(page_number)
        if hits:
            result[family] = hits[:12]
    return result


def needs_ocr(pages: list[str]) -> bool:
    text = "".join(pages)
    visible = re.sub(r"\s+", "", text)
    if len(visible) < 500:
        return True
    cjk = len(re.findall(r"[\u3400-\u9fff]", visible))
    page_density = len(visible) / max(1, len(pages))
    return page_density < 180 or cjk / len(visible) < 0.15


def infer_title(path: Path, first_page: str) -> str:
    stem = path.stem.strip()
    if not GENERIC_STEM.fullmatch(stem) and TITLE_HINT.search(stem):
        return stem
    candidates = []
    for raw_line in first_page.splitlines()[:40]:
        line = re.sub(r"\s+", "", raw_line).strip("-—_：:，,。·")
        if not 6 <= len(line) <= 48:
            continue
        if re.search(r"摘要|关键词|参赛|编号|大学|学院|^本文", line) or TITLE_NOISE.search(line):
            continue
        if not candidates:
            candidates.append(line)
        if TITLE_HINT.search(line):
            return line
    return candidates[0] if candidates else "未识别标题"


def public_source_label(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    year_match = YEAR_PATTERN.search(relative)
    year = year_match.group() if year_match else "unknown-year"
    return f"{year}/paper-{file_sha256(path)[:12]}{path.suffix.lower()}"


def summarize_pdf(path: Path, root: Path, ocr_mode: str, ocr_cache: Path) -> dict[str, object]:
    pages, page_count = extract_text_layer(path)
    extraction = "text-layer"
    if needs_ocr(pages) and ocr_mode != "none":
        ocr_pages = ocr_pdf(path, page_count, ocr_cache, ocr_mode)
        if sum(len(page) for page in ocr_pages) >= 500:
            pages = ocr_pages
            extraction = f"ocr-{ocr_mode}"
    text = "\n".join(page for page in pages if page)
    relative = path.relative_to(root).as_posix()
    year_match = YEAR_PATTERN.search(relative)
    method_hits = term_hits(text, METHOD_TERMS)
    validation_hits = term_hits(text, VALIDATION_TERMS)
    return {
        "year": int(year_match.group()) if year_match else None,
        "title": infer_title(path, pages[0] if pages else ""),
        "source": public_source_label(path, root),
        "pages": page_count,
        "characters": len(text),
        "extraction": extraction if text else "empty",
        "methodFamilies": method_hits,
        "methodPages": term_pages(pages, METHOD_TERMS),
        "validationSignals": validation_hits,
        "validationPages": term_pages(pages, VALIDATION_TERMS),
    }


def render_markdown(records: list[dict[str, object]]) -> str:
    lines = [
        "# 2009-2023 国赛 A 题优秀论文语料索引",
        "",
        "> 本表由全文文本层与必要 OCR 的确定性关键词扫描生成，用于检索路由，不替代逐页审读。方法是否真正构成主模型，必须回到原论文核验。",
        "",
        f"共收录 {len(records)} 份 PDF；年份范围 {min(record['year'] for record in records if record['year'])}-{max(record['year'] for record in records if record['year'])}。",
        "",
        "## 逐年索引",
        "",
        "| 年份 | 论文 | 页数 | 文本来源 | 方法族 | 验证信号 |",
        "|---:|---|---:|---|---|---|",
    ]
    for record in records:
        methods = "、".join(record["methodFamilies"].keys()) or "未自动识别"
        validation = "、".join(record["validationSignals"].keys()) or "未自动识别"
        title = str(record["title"]).replace("|", "\\|")
        lines.append(
            f"| {record['year'] or ''} | {title} | {record['pages']} | {record['extraction']} | {methods} | {validation} |"
        )

    method_counts: Counter[str] = Counter()
    validation_counts: Counter[str] = Counter()
    for record in records:
        method_counts.update(record["methodFamilies"].keys())
        validation_counts.update(record["validationSignals"].keys())
    lines.extend(["", "## 语料级检索信号", "", "### 方法族覆盖", ""])
    lines.extend(f"- {name}: {count} 篇命中" for name, count in method_counts.most_common())
    lines.extend(["", "### 验证信号覆盖", ""])
    lines.extend(f"- {name}: {count} 篇命中" for name, count in validation_counts.most_common())
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 关键词命中只用于选择要读取的论文和页段，不能据此声称论文采用了某模型。",
            "- `ocr-representative` 只覆盖前 20 页与末 10 页；需要核验中间公式、图表或附录时必须读取原 PDF。",
            "- 论文中的方法与结论是历史样本，不是新赛题的默认答案；先建立简单可解释基线，再决定是否引入复杂算法。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_utf8_lf(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic method index for CUMCM A-paper PDFs.")
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
        records.append(summarize_pdf(path, root, args.ocr, args.ocr_cache.resolve()))
    records.sort(key=lambda record: (record["year"] or 0, str(record["source"]).casefold()))

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    write_utf8_lf(args.json_output, json.dumps(records, ensure_ascii=False, indent=2) + "\n")
    write_utf8_lf(args.markdown_output, render_markdown(records))
    print(f"Wrote {len(records)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
