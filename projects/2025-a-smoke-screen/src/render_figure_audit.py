"""Build a deterministic, paper-order figure QA bundle.

The contact sheets are internal review aids.  They are assembled from the
checked-in MATLAB PNG exports and must never be included in the manuscript or
appendix.  A PASS is issued only when the independent page-by-page PDF review
is bound to the current manuscript hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
VALID_REVIEW_TYPES = {"human_page_by_page", "codex_page_by_page_visual"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"JSON 顶层必须是对象：{path}")
    return loaded


def _font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/msyhbd.ttc") if bold else Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf") if bold else Path("C:/Windows/Fonts/arial.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _wrap_label(text: str, width: int = 42) -> list[str]:
    compact = " ".join(str(text).split())
    if not compact:
        return []
    return textwrap.wrap(
        compact,
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
    )[:2]


def _contact_sheet(
    entries: Iterable[dict[str, str]],
    destination: Path,
    *,
    grayscale: bool,
) -> None:
    entries = list(entries)
    if not entries:
        raise ValueError("正式图顺序为空，不能生成联系表")

    columns = 2
    page_width = 1800
    margin = 48
    gutter = 36
    tile_width = (page_width - 2 * margin - gutter) // columns
    tile_height = 600
    rows = (len(entries) + columns - 1) // columns
    page_height = 86 + rows * tile_height + max(0, rows - 1) * gutter + margin
    sheet = Image.new("RGB", (page_width, page_height), "white")
    draw = ImageDraw.Draw(sheet)
    title_font = _font(31, bold=True)
    label_font = _font(23, bold=True)
    claim_font = _font(19)
    draw.text(
        (margin, 26),
        "正式图灰度审计（内部）" if grayscale else "正式图顺序审计（内部）",
        fill="#222222",
        font=title_font,
    )

    for index, entry in enumerate(entries):
        row, column = divmod(index, columns)
        left = margin + column * (tile_width + gutter)
        top = 86 + row * (tile_height + gutter)
        right = left + tile_width
        bottom = top + tile_height
        draw.rectangle((left, top, right, bottom), outline="#B7B7B7", width=2)
        header = f"{entry['id']}  |  {entry['visual_grammar']}"
        draw.text((left + 18, top + 14), header, fill="#222222", font=label_font)

        image = Image.open(entry["png"]).convert("RGB")
        if grayscale:
            image = ImageOps.grayscale(image).convert("RGB")
        image.thumbnail((tile_width - 36, 438), Image.Resampling.LANCZOS)
        image_left = left + (tile_width - image.width) // 2
        image_top = top + 62 + (438 - image.height) // 2
        sheet.paste(image, (image_left, image_top))

        claim_lines = _wrap_label(entry["claim"])
        claim_top = top + 514
        for line_index, line in enumerate(claim_lines):
            draw.text(
                (left + 18, claim_top + line_index * 27),
                line,
                fill="#4A4A4A",
                font=claim_font,
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(destination, format="PNG", dpi=(150, 150), optimize=True)


def _audit_record(project_root: Path, record: dict[str, Any]) -> dict[str, Any]:
    intent = record.get("figure_intent", {})
    if not isinstance(intent, dict):
        intent = {}
    files = [str(item) for item in record.get("files", [])]
    artifacts: dict[str, str] = {}
    for relative in files:
        path = project_root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"图件缺失：{relative}")
        artifacts[relative] = sha256(path)
        expected = str(record.get("sha256", {}).get(relative, ""))
        if expected != artifacts[relative]:
            raise ValueError(f"图件哈希与清单不一致：{relative}")

    visual_grammar = str(
        intent.get("visual_grammar") or intent.get("template") or "unspecified"
    )
    claim = str(
        intent.get("reader_takeaway")
        or record.get("interpretation")
        or record.get("caption")
        or ""
    )
    return {
        "figure_id": str(record.get("id", "")),
        "role": str(record.get("role", "")),
        "display_decision": intent.get(
            "display_decision",
            {"decision": "figure" if record.get("role") == "paper" else "support"},
        ),
        "claim": claim,
        "visual_grammar": visual_grammar,
        "line_applicability": intent.get("line_applicability", {"recorded": False}),
        "evidence_signature": intent.get(
            "evidence_signature",
            {
                "data_source": record.get("data_source", ""),
                "semantic_layers": intent.get("semantic_layers", []),
            },
        ),
        "nearest_figure": intent.get("nearest_figure"),
        "why_not_merge": intent.get("why_not_merge"),
        "color_budget": intent.get("color_budget", {"recorded": False}),
        "panel_contract": intent.get("panel_contract", intent.get("semantic_layers", [])),
        "artifacts": artifacts,
    }


def build_audit(project_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    manifest_path = project_root / "figures" / "figure_manifest.json"
    paper_path = project_root / "paper" / "main.pdf"
    manual_review_path = project_root / "support" / "manual_pdf_qa.json"
    output_dir = project_root / "support" / "figure-audit"
    if not paper_path.is_file() or paper_path.stat().st_size == 0:
        raise FileNotFoundError("缺少最终论文 paper/main.pdf")

    manifest = load_json(manifest_path)
    records = manifest.get("figures", [])
    if not isinstance(records, list):
        raise ValueError("figure_manifest.json 缺少 figures 列表")
    by_id = {
        str(record.get("id")): record
        for record in records
        if isinstance(record, dict)
    }
    paper_order = [str(item) for item in manifest.get("paper_order", [])]
    declared_paper_ids = {
        figure_id
        for figure_id, record in by_id.items()
        if record.get("role") == "paper"
    }
    if not paper_order or set(paper_order) != declared_paper_ids or len(paper_order) != len(set(paper_order)):
        raise ValueError("paper_order 必须与 role=paper 的图件逐一对应且不得重复")

    audit_records = [_audit_record(project_root, by_id[figure_id]) for figure_id in paper_order]
    contact_entries: list[dict[str, str]] = []
    for audit_record in audit_records:
        png_paths = [
            path
            for path in audit_record["artifacts"]
            if Path(path).suffix.lower() == ".png"
        ]
        if len(png_paths) != 1:
            raise ValueError(f"{audit_record['figure_id']} 必须恰有一个 PNG")
        contact_entries.append(
            {
                "id": audit_record["figure_id"],
                "visual_grammar": audit_record["visual_grammar"],
                "claim": audit_record["claim"],
                "png": str(project_root / png_paths[0]),
            }
        )

    color_sheet = output_dir / "figure-contact-sheet.png"
    gray_sheet = output_dir / "figure-contact-sheet-gray.png"
    _contact_sheet(contact_entries, color_sheet, grayscale=False)
    _contact_sheet(contact_entries, gray_sheet, grayscale=True)

    pdf_hash = sha256(paper_path)
    manual_review: dict[str, Any] = {}
    if manual_review_path.is_file():
        manual_review = load_json(manual_review_path)
    review_current = bool(
        manual_review.get("status") == "PASS"
        and manual_review.get("review_type") in VALID_REVIEW_TYPES
        and manual_review.get("reviewed_pdf") == "paper/main.pdf"
        and manual_review.get("reviewed_pdf_sha256") == pdf_hash
    )
    human_review = {
        "status": "PASS" if review_current else "PENDING",
        "review_type": manual_review.get("review_type"),
        "reviewer_record": manual_review.get("reviewer_record"),
        "reviewed_at_local": manual_review.get("reviewed_at_local"),
        "reviewed_pdf_sha256": manual_review.get("reviewed_pdf_sha256"),
        "required_checks": [
            "continuous-paper-not-dashboard",
            "no-decorative-cards-or-pastel-panels",
            "each-panel-adds-unique-evidence",
            "line-and-color-gates-pass-in-grayscale",
            "readable-at-final-pdf-size",
            "appendix-is-typeset-evidence-not-screenshot-wall",
        ],
    }
    audit = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": {
            "path": "src/render_figure_audit.py",
            "sha256": sha256(project_root / "src" / "render_figure_audit.py"),
            "command": "python -B src/render_figure_audit.py",
        },
        "scope": "internal QA only; never include contact sheets in the manuscript or appendix",
        "paper_order": paper_order,
        "paper_order_sha256": canonical_hash(paper_order),
        "figures": audit_records,
        "contact_sheets": {
            "color": {
                "path": color_sheet.relative_to(project_root).as_posix(),
                "sha256": sha256(color_sheet),
            },
            "grayscale": {
                "path": gray_sheet.relative_to(project_root).as_posix(),
                "sha256": sha256(gray_sheet),
            },
        },
        "manuscript": {"path": "paper/main.pdf", "sha256": pdf_hash},
        "human_paper_style_review": human_review,
        "status": "pass" if review_current else "pending_human_review",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "figure_audit.json"
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output_dir / "figure_audit.json.sha256").write_text(
        f"{sha256(audit_path)}  figure_audit.json\n",
        encoding="ascii",
        newline="\n",
    )
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT,
        help="2025 A 题项目根目录",
    )
    args = parser.parse_args()
    audit = build_audit(args.project_root)
    print(
        "Figure audit built: "
        f"{len(audit['paper_order'])} paper figures; status={audit['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
