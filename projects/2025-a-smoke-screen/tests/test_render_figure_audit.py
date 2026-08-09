"""Regression tests for the figure and appendix evidence QA gates."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import render_figure_audit  # noqa: E402
import run_all  # noqa: E402


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_png(path: Path, color: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (160, 100), color).save(path, format="PNG")


def _figure_record(
    root: Path,
    *,
    figure_id: str,
    role: str,
    stem: str,
) -> dict[str, object]:
    relative = f"figures/{stem}.png"
    return {
        "id": figure_id,
        "role": role,
        "files": [relative],
        "sha256": {relative: render_figure_audit.sha256(root / relative)},
        "caption": f"{figure_id} caption",
        "figure_intent": {
            "visual_grammar": f"grammar_{figure_id.lower()}",
            "reader_takeaway": f"{figure_id} carries unique evidence.",
        },
    }


def _make_figure_project(root: Path) -> dict[str, object]:
    (root / "src").mkdir(parents=True)
    (root / "src" / "render_figure_audit.py").write_text(
        "# fixture generator\n", encoding="utf-8"
    )
    _write_png(root / "figures" / "f1.png", "#36566B")
    _write_png(root / "figures" / "f2.png", "#8A5A3B")
    _write_png(root / "figures" / "f3.png", "#777777")
    manifest: dict[str, object] = {
        "paper_order": ["F2", "F1"],
        "figures": [
            _figure_record(root, figure_id="F1", role="paper", stem="f1"),
            _figure_record(root, figure_id="F2", role="paper", stem="f2"),
            _figure_record(root, figure_id="F3", role="support", stem="f3"),
        ],
    }
    _write_json(root / "figures" / "figure_manifest.json", manifest)

    paper = root / "paper" / "main.pdf"
    paper.parent.mkdir(parents=True)
    paper.write_bytes(b"current-pdf-fixture")
    _write_json(
        root / "support" / "manual_pdf_qa.json",
        {
            "status": "PASS",
            "review_type": "human_page_by_page",
            "reviewed_pdf": "paper/main.pdf",
            "reviewed_pdf_sha256": render_figure_audit.sha256(paper),
            "reviewer_record": "fixture reviewer",
            "reviewed_at_local": "2026-08-09",
        },
    )
    return manifest


def _appendix_source_record(root: Path, *, selection: bool) -> dict[str, object]:
    source = root / "src" / "evidence_source.py"
    record: dict[str, object] = {
        "path": "src/evidence_source.py",
        "sha256": run_all._sha256(source),
    }
    if selection:
        record["selection"] = {"kind": "line_range", "start": 1, "end": 1}
    return record


def _make_appendix_project(root: Path) -> dict[str, object]:
    appendix_dir = root / "support" / "appendix-evidence"
    appendix_dir.mkdir(parents=True)
    (root / "src").mkdir(parents=True, exist_ok=True)
    generator = root / "src" / "render_appendix_evidence.py"
    requirements = root / "requirements-formal.txt"
    source = root / "src" / "evidence_source.py"
    validation = root / "validation" / "source.json"
    generator.write_text("# fixture generator\n", encoding="utf-8")
    requirements.write_text("openpyxl==3.1.5\n", encoding="utf-8")
    source.write_text("value = 1\n", encoding="utf-8")
    _write_json(validation, {"verified": True})
    paper = root / "paper" / "main.tex"
    paper.parent.mkdir(parents=True)
    paper.write_text("\\section{Appendix}\n", encoding="utf-8")

    artifacts: list[dict[str, object]] = []
    for index in range(4):
        relative = f"support/appendix-evidence/preview_{index}.svg"
        artifact = root / relative
        artifact.write_text(f"<svg><text>{index}</text></svg>\n", encoding="utf-8")
        artifacts.append(
            {
                "path": relative,
                "sha256": run_all._sha256(artifact),
                "evidence_type": "plain_vector_qa_preview_not_embedded_in_paper",
                "width_px": 3200,
                "height_px": 1800,
                "sources": [_appendix_source_record(root, selection=True)],
            }
        )

    fragments: list[dict[str, object]] = []
    for index in range(8):
        relative = f"support/appendix-evidence/fragment_{index}.tex"
        fragment = root / relative
        fragment.write_text(f"row {index} \\\\\n", encoding="utf-8")
        fragments.append(
            {
                "path": relative,
                "sha256": run_all._sha256(fragment),
                "kind": "searchable_latex_table_rows",
                "sources": [_appendix_source_record(root, selection=False)],
            }
        )

    manifest: dict[str, object] = {
        "schema_version": 2,
        "status": "reproducible",
        "appendix_policy": {
            "screenshots_embedded_in_paper": 0,
            "paper_format": "searchable native LaTeX",
            "qa_previews": "plain SVG, not embedded",
        },
        "generator": {
            "path": "src/render_appendix_evidence.py",
            "sha256": run_all._sha256(generator),
            "command": "python -B src/render_appendix_evidence.py",
            "requirements_path": "requirements-formal.txt",
            "requirements_sha256": run_all._sha256(requirements),
        },
        "source_validation": {
            "path": "validation/source.json",
            "sha256": run_all._sha256(validation),
            "workbook_hash_match": {"fixture.xlsx": True},
            "claim_checks": {"fixture_claim": True},
        },
        "artifacts": artifacts,
        "latex_fragments": fragments,
    }
    _write_json(appendix_dir / "manifest.json", manifest)
    return manifest


class FigureAuditBuildTests(unittest.TestCase):
    def test_paper_order_matches_paper_roles_and_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _make_figure_project(root)

            audit = render_figure_audit.build_audit(root)

            self.assertEqual(audit["paper_order"], ["F2", "F1"])
            self.assertEqual(
                [record["figure_id"] for record in audit["figures"]],
                ["F2", "F1"],
            )
            self.assertEqual(
                [record["role"] for record in audit["figures"]],
                ["paper", "paper"],
            )

            invalid_orders = (["F1"], ["F2", "F1", "F3"], ["F2", "F1", "F1"])
            for invalid_order in invalid_orders:
                with self.subTest(paper_order=invalid_order):
                    invalid = deepcopy(manifest)
                    invalid["paper_order"] = invalid_order
                    _write_json(root / "figures" / "figure_manifest.json", invalid)
                    with self.assertRaisesRegex(ValueError, "paper_order"):
                        render_figure_audit.build_audit(root)

    def test_tampered_figure_is_rejected_before_contact_sheet_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_figure_project(root)
            (root / "figures" / "f2.png").write_bytes(b"tampered-figure")

            with self.assertRaisesRegex(ValueError, "\u56fe\u4ef6\u54c8\u5e0c"):
                render_figure_audit.build_audit(root)

    def test_manual_review_pass_is_bound_to_the_current_pdf_hash_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_figure_project(root)

            current = render_figure_audit.build_audit(root)
            self.assertEqual(current["status"], "pass")
            self.assertEqual(
                current["human_paper_style_review"]["status"], "PASS"
            )

            paper = root / "paper" / "main.pdf"
            paper.write_bytes(b"new-pdf-after-review")
            stale = render_figure_audit.build_audit(root)
            self.assertEqual(stale["status"], "pending_human_review")
            self.assertEqual(stale["human_paper_style_review"]["status"], "PENDING")
            self.assertEqual(stale["manuscript"]["sha256"], run_all._sha256(paper))

            manual_path = root / "support" / "manual_pdf_qa.json"
            manual = json.loads(manual_path.read_text(encoding="utf-8"))
            manual["reviewed_pdf_sha256"] = run_all._sha256(paper)
            manual["reviewed_pdf"] = "paper/other.pdf"
            _write_json(manual_path, manual)
            wrong_path = render_figure_audit.build_audit(root)
            self.assertEqual(wrong_path["status"], "pending_human_review")


class FigureAuditRunAllGateTests(unittest.TestCase):
    def _gate_patches(self, root: Path):
        return patch.multiple(
            run_all,
            ROOT=root,
            PAPER_PDF_PATH=root / "paper" / "main.pdf",
            FIGURE_AUDIT_PATH=root / "support" / "figure-audit" / "figure_audit.json",
            FIGURE_AUDIT_HASH_PATH=(
                root / "support" / "figure-audit" / "figure_audit.json.sha256"
            ),
        )

    def test_contact_sheet_and_audit_sidecar_hashes_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _make_figure_project(root)
            audit = render_figure_audit.build_audit(root)
            audit_path = root / "support" / "figure-audit" / "figure_audit.json"
            sidecar = root / "support" / "figure-audit" / "figure_audit.json.sha256"

            for record in audit["contact_sheets"].values():
                self.assertEqual(
                    record["sha256"], run_all._sha256(root / record["path"])
                )
            self.assertEqual(
                sidecar.read_text(encoding="ascii").split()[0],
                run_all._sha256(audit_path),
            )
            with self._gate_patches(root):
                self.assertEqual(run_all._figure_audit_errors(manifest), [])

                color_sheet = root / audit["contact_sheets"]["color"]["path"]
                color_sheet.write_bytes(color_sheet.read_bytes() + b"tamper")
                self.assertIn(
                    "contact-sheet:color",
                    run_all._figure_audit_errors(manifest),
                )

            render_figure_audit.build_audit(root)
            audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
            audit_payload["scope"] = "tampered after generation"
            _write_json(audit_path, audit_payload)
            with self._gate_patches(root):
                self.assertIn(
                    "audit-hash:mismatch",
                    run_all._figure_audit_errors(manifest),
                )

    def test_gate_rejects_manifest_paper_order_role_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _make_figure_project(root)
            render_figure_audit.build_audit(root)
            divergent = deepcopy(manifest)
            divergent["figures"][1]["role"] = "support"

            with self._gate_patches(root):
                self.assertIn(
                    "paper-role-order",
                    run_all._figure_audit_errors(divergent),
                )

    def test_gate_binds_audited_artifacts_to_manifest_and_current_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _make_figure_project(root)
            render_figure_audit.build_audit(root)
            figure = root / "figures" / "f2.png"
            figure.write_bytes(b"post-audit-tamper")

            with self._gate_patches(root):
                errors = run_all._figure_audit_errors(manifest)
                self.assertIn("figure:F2:hash:f2.png", errors)

                updated_manifest = deepcopy(manifest)
                updated_manifest["figures"][1]["sha256"]["figures/f2.png"] = (
                    run_all._sha256(figure)
                )
                self.assertIn(
                    "figure:F2:artifacts",
                    run_all._figure_audit_errors(updated_manifest),
                )

    def test_gate_rejects_audit_role_or_order_tamper_even_with_new_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _make_figure_project(root)
            render_figure_audit.build_audit(root)
            audit_path = root / "support" / "figure-audit" / "figure_audit.json"
            sidecar = root / "support" / "figure-audit" / "figure_audit.json.sha256"

            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["figures"][0]["role"] = "support"
            _write_json(audit_path, audit)
            sidecar.write_text(
                f"{run_all._sha256(audit_path)}  figure_audit.json\n",
                encoding="ascii",
            )
            with self._gate_patches(root):
                self.assertIn(
                    "figure:F2:role",
                    run_all._figure_audit_errors(manifest),
                )

            render_figure_audit.build_audit(root)
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            audit["figures"].reverse()
            _write_json(audit_path, audit)
            sidecar.write_text(
                f"{run_all._sha256(audit_path)}  figure_audit.json\n",
                encoding="ascii",
            )
            with self._gate_patches(root):
                self.assertIn(
                    "figures:order",
                    run_all._figure_audit_errors(manifest),
                )


class AppendixEvidenceRunAllGateTests(unittest.TestCase):
    def _gate_patches(self, root: Path):
        return patch.multiple(
            run_all,
            ROOT=root,
            PAPER_TEX_PATH=root / "paper" / "main.tex",
            APPENDIX_EVIDENCE_MANIFEST_PATH=(
                root / "support" / "appendix-evidence" / "manifest.json"
            ),
        )

    def test_valid_typeset_evidence_passes_and_hash_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = _make_appendix_project(root)
            with self._gate_patches(root):
                self.assertEqual(run_all._appendix_evidence_errors(), [])

                artifact = root / manifest["artifacts"][0]["path"]
                artifact.write_text("<svg>tampered</svg>\n", encoding="utf-8")
                errors = run_all._appendix_evidence_errors()
                self.assertIn(f"artifact:{manifest['artifacts'][0]['path']}", errors)

    def test_source_tampering_and_embedded_preview_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_appendix_project(root)
            source = root / "src" / "evidence_source.py"
            source.write_text("value = 2\n", encoding="utf-8")
            (root / "paper" / "main.tex").write_text(
                "\\includegraphics{../support/appendix-evidence/preview_0.svg}\n",
                encoding="utf-8",
            )

            with self._gate_patches(root):
                errors = run_all._appendix_evidence_errors()

            self.assertIn("appendix-policy:embedded-preview", errors)
            self.assertTrue(any(error.startswith("source-hash:") for error in errors))
            self.assertTrue(
                any(error.startswith("latex-source-hash:") for error in errors)
            )


if __name__ == "__main__":
    unittest.main()
