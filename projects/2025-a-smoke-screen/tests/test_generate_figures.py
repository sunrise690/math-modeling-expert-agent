"""Regression tests for the MATLAB-only figure provenance gate."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import generate_figures  # noqa: E402


class MatlabFigureManifestTests(unittest.TestCase):
    def test_matlab_log_sanitizer_keeps_metrics_and_drops_local_paths(self) -> None:
        output = (
            "Rendered event evidence:\n"
            "  C:\\Users\\person\\project\\figure.png\n"
            "objective 4.832502 s\n"
            "Rendered in D:/private/project/figures\n"
        )

        sanitized = generate_figures._sanitize_matlab_stdout(output)

        self.assertEqual(
            sanitized,
            "Rendered event evidence:\nobjective 4.832502 s",
        )
        self.assertNotIn("Users", sanitized)

    def test_svg_normalization_only_removes_trailing_whitespace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            svg = root / "figure.svg"
            png = root / "figure.png"
            svg.write_bytes(
                b"<svg>   \r\n  <path d='M0 0' /> \t\r\n</svg>\r\n"
            )
            png.write_bytes(b"not-an-svg  \n")

            generate_figures._normalize_svg_whitespace([svg, png])

            self.assertEqual(
                svg.read_text(encoding="utf-8"),
                "<svg>\n  <path d='M0 0' />\n</svg>\n",
            )
            self.assertEqual(png.read_bytes(), b"not-an-svg  \n")

    def test_dependency_provenance_requires_exact_source_and_input_binding(self) -> None:
        current = {
            "schema_version": 1,
            "sources_sha256": {"src/matlab/a.m": "a" * 64},
            "inputs_sha256": {"validation/a.json": "b" * 64},
        }
        with self.assertRaisesRegex(RuntimeError, "缺少 MATLAB.*依赖哈希"):
            generate_figures._validate_dependency_provenance({}, current)
        self.assertIsNone(
            generate_figures._validate_dependency_provenance(
                {"matlab_provenance": current}, current
            )
        )
        changed = {
            **current,
            "inputs_sha256": {"validation/a.json": "c" * 64},
        }
        with self.assertRaisesRegex(RuntimeError, "MATLAB.*JSON"):
            generate_figures._validate_dependency_provenance(
                {"matlab_provenance": current}, changed
            )

    def test_reuse_requires_renderer_nonempty_files_and_exact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            figure_dir = root / "figures"
            figure_dir.mkdir()
            files = generate_figures.figure_files("only")
            for index, relative_path in enumerate(files):
                (root / relative_path).write_bytes(f"artifact-{index}".encode())
            record = {
                "id": "F1",
                "renderer": "MATLAB R2026a",
                "files": files,
                "sha256": {
                    relative_path: generate_figures.sha256(root / relative_path)
                    for relative_path in files
                },
            }
            manifest = {"figures": [record]}
            with (
                patch.object(generate_figures, "ROOT", root),
                patch.object(generate_figures, "FIGURE_STEMS", ("only",)),
            ):
                generate_figures._validate_reusable_manifest(manifest)
                (root / files[0]).write_bytes(b"tampered")
                with self.assertRaisesRegex(RuntimeError, "hash"):
                    generate_figures._validate_reusable_manifest(manifest)

            record["renderer"] = "matplotlib"
            record["sha256"][files[0]] = generate_figures.sha256(root / files[0])
            with (
                patch.object(generate_figures, "ROOT", root),
                patch.object(generate_figures, "FIGURE_STEMS", ("only",)),
                self.assertRaisesRegex(RuntimeError, "renderer"),
            ):
                generate_figures._validate_reusable_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
