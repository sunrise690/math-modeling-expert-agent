"""Render deterministic appendix screenshots from checked project evidence.

The images are not synthetic mock-ups: code panels are copied verbatim from
the indicated source ranges and table panels are read directly from the three
submission workbooks.  Relative paths and SHA-256 prefixes make every panel
traceable without exposing a machine-local absolute path.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "support" / "appendix-evidence"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"

PAPER = "#FAFAF7"
INK = "#1E2A32"
MUTED = "#647078"
GRID = "#D6DEE1"
PANEL = "#F1F4F2"
PRIMARY = "#2F6079"
SECONDARY = "#3D7A70"
WARM = "#B5782F"
WINE = "#8B4E5A"


def _font_path(*candidates: str) -> Path:
    for candidate in candidates:
        path = Path("C:/Windows/Fonts") / candidate
        if path.is_file():
            return path
    raise FileNotFoundError(f"No requested Windows font is available: {candidates}")


MONO = _font_path("consola.ttf", "cour.ttf")
MONO_BOLD = _font_path("consolab.ttf", "courbd.ttf")
SANS = _font_path("msyh.ttc", "simhei.ttf")
SANS_BOLD = _font_path("msyhbd.ttc", "simhei.ttf")


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size=size)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _rounded_rectangle(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    *,
    radius: int = 12,
    fill: str = PAPER,
    outline: str = GRID,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _header(
    draw: ImageDraw.ImageDraw,
    *,
    title: str,
    subtitle: str,
    width: int,
    title_y: int = 54,
) -> int:
    draw.text((70, title_y), title, font=_font(SANS_BOLD, 40), fill=INK)
    draw.text((70, title_y + 60), subtitle, font=_font(SANS, 23), fill=MUTED)
    draw.line((70, title_y + 108, width - 70, title_y + 108), fill=PRIMARY, width=4)
    return title_y + 140


def _wrap_code_line(line: str, width: int) -> list[str]:
    expanded = line.expandtabs(4)
    if len(expanded) <= width:
        return [expanded]
    indent = len(expanded) - len(expanded.lstrip())
    continuation = " " * min(indent + 4, 20)
    pieces = textwrap.wrap(
        expanded,
        width=width,
        subsequent_indent=continuation,
        break_long_words=False,
        break_on_hyphens=False,
        replace_whitespace=False,
        drop_whitespace=False,
    )
    return pieces or [expanded]


def _draw_code_panel(
    draw: ImageDraw.ImageDraw,
    *,
    box: tuple[int, int, int, int],
    source: Path,
    start: int,
    end: int,
    title: str,
) -> None:
    x0, y0, x1, y1 = box
    _rounded_rectangle(draw, box, fill="#FFFFFF")
    draw.rectangle((x0, y0, x1, y0 + 68), fill=PANEL)
    draw.text((x0 + 28, y0 + 17), title, font=_font(SANS_BOLD, 26), fill=INK)
    source_label = f"{_relative(source)}  L{start}–L{end}  sha256:{_sha256(source)[:12]}"
    draw.text((x0 + 28, y0 + 78), source_label, font=_font(MONO, 19), fill=MUTED)

    lines = source.read_text(encoding="utf-8").splitlines()
    selected = lines[start - 1 : end]
    code_font = _font(MONO, 38)
    code_bold = _font(MONO_BOLD, 38)
    line_font = _font(MONO, 31)
    line_height = 47
    y = y0 + 120
    max_chars = 61
    for line_number, raw in enumerate(selected, start=start):
        pieces = _wrap_code_line(raw, max_chars)
        for piece_index, piece in enumerate(pieces):
            if y + line_height > y1 - 22:
                raise RuntimeError(f"Code excerpt does not fit panel: {source}:{start}-{end}")
            number = f"{line_number:4d}" if piece_index == 0 else "    "
            draw.text((x0 + 22, y), number, font=line_font, fill="#8B959B")
            stripped = piece.lstrip()
            if stripped.startswith(("def ", "class ")):
                line_color = PRIMARY
                selected_font = code_bold
            elif stripped.startswith("#") or stripped.startswith(('"""', "'''")):
                line_color = SECONDARY
                selected_font = code_font
            elif stripped.startswith(("raise ", "assert ")):
                line_color = WINE
                selected_font = code_font
            else:
                line_color = INK
                selected_font = code_font
            draw.text((x0 + 88, y), piece, font=selected_font, fill=line_color)
            y += line_height


def render_code_evidence() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    geometry = ROOT / "src" / "geometry_engine.py"
    optimizer = ROOT / "src" / "optimizer.py"

    specifications = [
        (
            OUTPUT_DIR / "appendix_code_geometry.png",
            "附录代码证据 A：有限视线几何与连续事件",
            "代码逐行取自正式求解源文件；左侧为有限线段距离，右侧为根区间扫描与 Brent 连续求根。",
            geometry,
            (259, 279, "有限视线距离与投影参数"),
            geometry,
            (552, 571, "Brent 连续求根与根集合"),
        ),
        (
            OUTPUT_DIR / "appendix_code_optimizer.png",
            "附录代码证据 B：组合搜索与精确复算",
            "代码逐行取自正式优化源文件；截图保留真实行号、相对路径和文件哈希，完整程序随电子材料提交。",
            optimizer,
            (470, 490, "同航路候选组合筛选"),
            optimizer,
            (1117, 1137, "问题五有限状态搜索入口"),
        ),
    ]

    rendered: list[Path] = []
    for output, title, subtitle, left_source, left_spec, right_source, right_spec in specifications:
        image = Image.new("RGB", (3200, 1900), PAPER)
        draw = ImageDraw.Draw(image)
        content_y = _header(draw, title=title, subtitle=subtitle, width=image.width)
        panel_top = content_y + 10
        panel_bottom = image.height - 70
        _draw_code_panel(
            draw,
            box=(70, panel_top, 1575, panel_bottom),
            source=left_source,
            start=left_spec[0],
            end=left_spec[1],
            title=left_spec[2],
        )
        _draw_code_panel(
            draw,
            box=(1625, panel_top, 3130, panel_bottom),
            source=right_source,
            start=right_spec[0],
            end=right_spec[1],
            title=right_spec[2],
        )
        image.save(output, format="PNG", optimize=True)
        rendered.append(output)
    return rendered


def _format_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if abs(value) < 5e-8:
            return "0.0000"
        return f"{value:.4f}"
    return str(value)


def _workbook_values(path: Path) -> tuple[str, list[list[object]]]:
    workbook = load_workbook(path, data_only=False, read_only=True)
    worksheet = workbook[workbook.sheetnames[0]]
    raw_rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
    if not raw_rows:
        return worksheet.title, []
    rows = [raw_rows[0]]
    for row in raw_rows[1:]:
        if not any(value is not None and str(value).strip() for value in row):
            break
        rows.append(row)
    return worksheet.title, rows


def _workbook_rows(path: Path) -> list[list[str]]:
    _, rows = _workbook_values(path)
    return [[_format_cell(value) for value in row] for row in rows]


def _workbook_snapshot(path: Path) -> dict[str, Any]:
    sheet, values = _workbook_values(path)
    formatted = [[_format_cell(value) for value in row] for row in values]
    column_count = len(formatted[0]) if formatted else 0
    row_count = len(formatted)
    normalized = json.dumps(formatted, ensure_ascii=False, separators=(",", ":"))
    selection = (
        f"{sheet}!A1:{get_column_letter(column_count)}{row_count}"
        if row_count and column_count
        else f"{sheet}!empty"
    )
    return {
        "path": _relative(path),
        "sha256": _sha256(path),
        "selection": selection,
        "active_row_count_including_header": row_count,
        "column_count": column_count,
        "display_precision_decimal_places": 4,
        "normalized_display_sha256": _sha256_text(normalized),
    }


def _code_snapshot(path: Path, start: int, end: int) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    excerpt = "\n".join(lines[start - 1 : end]) + "\n"
    return {
        "path": _relative(path),
        "sha256": _sha256(path),
        "selection": {"kind": "line_range", "start": start, "end": end},
        "normalized_excerpt_sha256": _sha256_text(excerpt),
    }


def _draw_table(
    draw: ImageDraw.ImageDraw,
    *,
    box: tuple[int, int, int, int],
    path: Path,
    title: str,
    font_size: int,
    header_height: int,
) -> None:
    x0, y0, x1, y1 = box
    rows = _workbook_rows(path)
    if not rows:
        raise RuntimeError(f"Workbook is empty: {path}")
    column_count = len(rows[0])
    _rounded_rectangle(draw, box, fill="#FFFFFF")
    draw.rectangle((x0, y0, x1, y0 + 64), fill=PANEL)
    draw.text((x0 + 24, y0 + 14), title, font=_font(SANS_BOLD, 25), fill=INK)
    meta = f"{_relative(path)}  sha256:{_sha256(path)[:12]}  显示精度：小数点后 4 位"
    draw.text((x1 - 24, y0 + 18), meta, font=_font(SANS, 18), fill=MUTED, anchor="ra")

    table_top = y0 + 78
    table_bottom = y1 - 22
    data_rows = max(1, len(rows) - 1)
    row_height = (table_bottom - table_top - header_height) / data_rows
    widths = [max(8, len(str(header))) for header in rows[0]]
    total_weight = sum(min(26, width) for width in widths)
    boundaries = [x0 + 20]
    usable_width = x1 - x0 - 40
    consumed = 0.0
    for width in widths:
        consumed += min(26, width) / total_weight * usable_width
        boundaries.append(x0 + 20 + consumed)

    header_font = _font(SANS_BOLD, max(17, font_size - 2))
    body_font = _font(SANS, font_size)
    for column in range(column_count):
        left = int(round(boundaries[column]))
        right = int(round(boundaries[column + 1]))
        draw.rectangle((left, table_top, right, table_top + header_height), fill="#E4ECEB", outline=GRID, width=2)
        header = rows[0][column]
        wrap_width = max(4, int((right - left) / max(10, font_size * 0.95)))
        wrapped = "\n".join(textwrap.wrap(header, width=wrap_width, break_long_words=True))
        draw.multiline_text(
            ((left + right) / 2, table_top + header_height / 2),
            wrapped,
            font=header_font,
            fill=INK,
            anchor="mm",
            align="center",
            spacing=3,
        )

    for row_index, row in enumerate(rows[1:]):
        top = int(round(table_top + header_height + row_index * row_height))
        bottom = int(round(table_top + header_height + (row_index + 1) * row_height))
        fill = "#FFFFFF" if row_index % 2 == 0 else "#F6F7F4"
        for column in range(column_count):
            left = int(round(boundaries[column]))
            right = int(round(boundaries[column + 1]))
            draw.rectangle((left, top, right, bottom), fill=fill, outline=GRID, width=1)
            value = row[column] if column < len(row) else ""
            draw.text(
                ((left + right) / 2, (top + bottom) / 2),
                value,
                font=body_font,
                fill=INK,
                anchor="mm",
            )


def render_workbook_evidence() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result1 = ROOT / "outputs" / "result1.xlsx"
    result2 = ROOT / "outputs" / "result2.xlsx"
    result3 = ROOT / "outputs" / "result3.xlsx"

    combined = OUTPUT_DIR / "appendix_data_result12.png"
    image = Image.new("RGB", (3200, 1900), PAPER)
    draw = ImageDraw.Draw(image)
    content_y = _header(
        draw,
        title="附录数据证据 A：问题三与问题四提交结果",
        subtitle="表格直接读取正式输出工作簿；空白模板行已隐藏，数值仅按显示精度格式化。",
        width=image.width,
    )
    _draw_table(
        draw,
        box=(70, content_y + 10, 3130, 1005),
        path=result1,
        title="问题三：FY1 三枚烟幕弹",
        font_size=23,
        header_height=150,
    )
    _draw_table(
        draw,
        box=(70, 1045, 3130, 1830),
        path=result2,
        title="问题四：FY1–FY3 各投放一枚烟幕弹",
        font_size=23,
        header_height=150,
    )
    image.save(combined, format="PNG", optimize=True)

    multi = OUTPUT_DIR / "appendix_data_result3.png"
    image = Image.new("RGB", (3600, 2050), PAPER)
    draw = ImageDraw.Draw(image)
    content_y = _header(
        draw,
        title="附录数据证据 B：问题五 15 枚烟幕弹联合方案",
        subtitle="完整展示 result3.xlsx 的 15 条有效记录与 12 个提交字段；截图由工作簿原值确定性生成。",
        width=image.width,
    )
    _draw_table(
        draw,
        box=(55, content_y + 10, 3545, 1985),
        path=result3,
        title="五机—多弹—三目标联合指派结果",
        font_size=20,
        header_height=145,
    )
    image.save(multi, format="PNG", optimize=True)
    return [combined, multi]


def _duration_sum(path: Path) -> tuple[int, float]:
    _, rows = _workbook_values(path)
    if len(rows) < 2:
        raise RuntimeError(f"Workbook has no active data rows: {path}")
    headers = [str(value) for value in rows[0]]
    try:
        duration_index = next(
            index for index, header in enumerate(headers) if "有效干扰时长" in header
        )
    except StopIteration as error:
        raise RuntimeError(f"Duration column not found: {path}") from error
    durations = [float(row[duration_index]) for row in rows[1:]]
    return len(durations), sum(durations)


def _artifact_record(
    artifact: Path,
    *,
    evidence_type: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    with Image.open(artifact) as image:
        width, height = image.size
    return {
        "path": _relative(artifact),
        "sha256": _sha256(artifact),
        "evidence_type": evidence_type,
        "width_px": width,
        "height_px": height,
        "sources": sources,
    }


def write_manifest(artifacts: list[Path]) -> dict[str, Any]:
    geometry = ROOT / "src" / "geometry_engine.py"
    optimizer = ROOT / "src" / "optimizer.py"
    result1 = ROOT / "outputs" / "result1.xlsx"
    result2 = ROOT / "outputs" / "result2.xlsx"
    result3 = ROOT / "outputs" / "result3.xlsx"
    validation_path = ROOT / "validation" / "q3_q5_independent.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))

    workbooks = {path.name: path for path in (result1, result2, result3)}
    source_workbook_hashes = validation.get("output_workbook_sha256", {})
    workbook_hash_match = {
        name: _sha256(path) == str(source_workbook_hashes.get(name, "")).lower()
        for name, path in workbooks.items()
    }
    row_counts: dict[str, int] = {}
    duration_sums: dict[str, float] = {}
    for name, path in workbooks.items():
        row_counts[name], duration_sums[name] = _duration_sum(path)

    exact_objectives = {
        question: float(validation["results"][question]["exact_centerline_objective"])
        for question in ("Q3", "Q4", "Q5")
    }
    expected_rows = {"result1.xlsx": 3, "result2.xlsx": 3, "result3.xlsx": 15}
    claim_checks = {
        "workbook_hashes_match_validation": all(workbook_hash_match.values()),
        "active_row_counts_match_submission_scope": row_counts == expected_rows,
        "q4_nonoverlap_sum_matches_union": abs(
            duration_sums["result2.xlsx"] - exact_objectives["Q4"]
        ) <= 1.0e-8,
        "q3_union_not_greater_than_row_sum": (
            exact_objectives["Q3"] <= duration_sums["result1.xlsx"] + 1.0e-8
        ),
        "q5_union_not_greater_than_row_sum": (
            exact_objectives["Q5"] <= duration_sums["result3.xlsx"] + 1.0e-8
        ),
    }
    if not all(claim_checks.values()):
        failed = [name for name, passed in claim_checks.items() if not passed]
        raise RuntimeError("Appendix evidence claim checks failed: " + ", ".join(failed))

    by_name = {path.name: path for path in artifacts}
    artifact_records = [
        _artifact_record(
            by_name["appendix_code_geometry.png"],
            evidence_type="verbatim_source_excerpt",
            sources=[
                _code_snapshot(geometry, 259, 279),
                _code_snapshot(geometry, 552, 571),
            ],
        ),
        _artifact_record(
            by_name["appendix_code_optimizer.png"],
            evidence_type="verbatim_source_excerpt",
            sources=[
                _code_snapshot(optimizer, 470, 490),
                _code_snapshot(optimizer, 1117, 1137),
            ],
        ),
        _artifact_record(
            by_name["appendix_data_result12.png"],
            evidence_type="normalized_workbook_table",
            sources=[_workbook_snapshot(result1), _workbook_snapshot(result2)],
        ),
        _artifact_record(
            by_name["appendix_data_result3.png"],
            evidence_type="normalized_workbook_table",
            sources=[_workbook_snapshot(result3)],
        ),
    ]
    renderer = Path(__file__).resolve()
    requirements = ROOT / "requirements-formal.txt"
    manifest = {
        "schema_version": 1,
        "status": "reproducible",
        "generator": {
            "path": _relative(renderer),
            "sha256": _sha256(renderer),
            "command": "python -B src/render_appendix_evidence.py",
            "python": sys.version.split()[0],
            "libraries": {
                "openpyxl": importlib.metadata.version("openpyxl"),
                "Pillow": importlib.metadata.version("Pillow"),
            },
            "requirements_path": _relative(requirements),
            "requirements_sha256": _sha256(requirements),
            "fonts": {
                MONO.name: _sha256(MONO),
                MONO_BOLD.name: _sha256(MONO_BOLD),
                SANS.name: _sha256(SANS),
                SANS_BOLD.name: _sha256(SANS_BOLD),
            },
        },
        "source_validation": {
            "path": _relative(validation_path),
            "sha256": _sha256(validation_path),
            "workbook_hash_match": workbook_hash_match,
            "active_data_rows": row_counts,
            "duration_row_sums_s": duration_sums,
            "exact_union_objectives_s": exact_objectives,
            "tolerance_s": 1.0e-8,
            "claim_checks": claim_checks,
        },
        "artifacts": artifact_records,
        "producer_dag": [
            {
                "output": record["path"],
                "producer": _relative(renderer),
                "inputs": [source["path"] for source in record["sources"]],
            }
            for record in artifact_records
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    artifacts = render_code_evidence() + render_workbook_evidence()
    for artifact in artifacts:
        with Image.open(artifact) as image:
            if image.width < 3000 or image.height < 1700:
                raise RuntimeError(f"Appendix evidence image is too small: {artifact}")
        print(f"{_relative(artifact)}  sha256:{_sha256(artifact)}")
    write_manifest(artifacts)
    print(f"{_relative(MANIFEST_PATH)}  sha256:{_sha256(MANIFEST_PATH)}")


if __name__ == "__main__":
    main()
