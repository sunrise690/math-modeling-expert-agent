"""Regression tests for the Origin Q5 multivariate evidence bundle."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import run_all  # noqa: E402
from origin.render_q5_multivariate import build_analysis  # noqa: E402


PROVENANCE_RELATIVE = Path("support/multivariate/q5_multivariate_provenance.json")
RUN_RELATIVE = Path("support/multivariate/q5_multivariate_run.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _copy_minimal_origin_closure(destination: Path) -> None:
    provenance = _read_json(PROJECT_ROOT / PROVENANCE_RELATIVE)
    recorded_paths = {
        PROVENANCE_RELATIVE.as_posix(),
        RUN_RELATIVE.as_posix(),
        str(provenance["source"]),
        str(provenance["input"]),
        str(provenance["palette_spec"]),
        str(provenance["capability_snapshot"]["path"]),
        str(provenance["graph_contract"]["path"]),
        *map(str, provenance["derived_data"]),
        *map(str, provenance["artifacts"]),
    }
    for relative in sorted(recorded_paths):
        source = PROJECT_ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _pairwise_distances(matrix: np.ndarray) -> np.ndarray:
    differences = matrix[:, None, :] - matrix[None, :, :]
    return np.linalg.norm(differences, axis=2)


class OriginMultivariateGateTests(unittest.TestCase):
    def test_current_origin_bundle_passes(self) -> None:
        self.assertEqual(run_all._origin_multivariate_errors(), [])

    def test_heading_group_is_rotation_invariant(self) -> None:
        validation = _read_json(PROJECT_ROOT / "validation/q3_q5_independent.json")
        rotated_validation = deepcopy(validation)
        for plan in rotated_validation["results"]["Q5"]["plans"]:
            plan["heading_deg"] = (float(plan["heading_deg"]) + 37.0) % 360.0

        baseline = build_analysis(validation)
        rotated = build_analysis(rotated_validation)

        for analysis in (baseline, rotated):
            heading_block = np.asarray(analysis["standardized"], dtype=float)[:, :2]
            total_sample_variance = float(
                np.var(heading_block, axis=0, ddof=1).sum()
            )
            self.assertAlmostEqual(total_sample_variance, 1.0, places=12)

        np.testing.assert_allclose(
            _pairwise_distances(baseline["standardized"][:, :2]),
            _pairwise_distances(rotated["standardized"][:, :2]),
            rtol=1.0e-12,
            atol=1.0e-12,
        )
        np.testing.assert_allclose(
            _pairwise_distances(baseline["standardized"]),
            _pairwise_distances(rotated["standardized"]),
            rtol=1.0e-12,
            atol=1.0e-12,
        )

        baseline_singular = np.linalg.svd(
            baseline["standardized"], compute_uv=False
        )
        rotated_singular = np.linalg.svd(
            rotated["standardized"], compute_uv=False
        )
        baseline_spectrum = baseline_singular**2 / (
            baseline["standardized"].shape[0] - 1
        )
        rotated_spectrum = rotated_singular**2 / (
            rotated["standardized"].shape[0] - 1
        )
        np.testing.assert_allclose(
            baseline_spectrum,
            rotated_spectrum,
            rtol=1.0e-11,
            atol=1.0e-12,
        )
        np.testing.assert_allclose(
            baseline["explained"],
            rotated["explained"],
            rtol=1.0e-11,
            atol=1.0e-12,
        )

    def test_weighted_z_tamper_fails_even_when_hash_chain_is_refreshed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _copy_minimal_origin_closure(root)
            self.assertEqual(run_all._origin_multivariate_errors(root), [])

            weighted_relative = Path(
                "support/multivariate/q5_multivariate_weighted_z.csv"
            )
            weighted_path = root / weighted_relative
            with weighted_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = list(reader.fieldnames or [])
                rows = list(reader)
            value_field = "weighted_z_heading_cos"
            rows[0][value_field] = format(float(rows[0][value_field]) + 0.125, ".17g")
            with weighted_path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            provenance_path = root / PROVENANCE_RELATIVE
            provenance = _read_json(provenance_path)
            provenance["derived_data"][weighted_relative.as_posix()] = _sha256(
                weighted_path
            )
            _write_json(provenance_path, provenance)

            run_path = root / RUN_RELATIVE
            run = _read_json(run_path)
            run["provenance_sha256"] = _sha256(provenance_path)
            _write_json(run_path, run)

            self.assertTrue(run_all._origin_multivariate_errors(root))

    def test_unverified_origin_exit_fails_even_when_hash_chain_is_refreshed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _copy_minimal_origin_closure(root)
            self.assertEqual(run_all._origin_multivariate_errors(root), [])

            provenance_path = root / PROVENANCE_RELATIVE
            provenance = _read_json(provenance_path)
            capability_relative = Path(provenance["capability_snapshot"]["path"])
            capability_path = root / capability_relative
            capability = _read_json(capability_path)
            capability["origin_exit_verified"] = False
            _write_json(capability_path, capability)

            capability_sha256 = _sha256(capability_path)
            provenance["capability_snapshot"]["sha256"] = capability_sha256
            _write_json(provenance_path, provenance)

            run_path = root / RUN_RELATIVE
            run = _read_json(run_path)
            run["capability_snapshot_sha256"] = capability_sha256
            run["provenance_sha256"] = _sha256(provenance_path)
            _write_json(run_path, run)

            self.assertTrue(run_all._origin_multivariate_errors(root))

    def test_unverified_project_roundtrip_fails_even_when_hash_chain_is_refreshed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _copy_minimal_origin_closure(root)
            self.assertEqual(run_all._origin_multivariate_errors(root), [])

            provenance_path = root / PROVENANCE_RELATIVE
            provenance = _read_json(provenance_path)
            capability_relative = Path(provenance["capability_snapshot"]["path"])
            capability_path = root / capability_relative
            capability = _read_json(capability_path)
            capability["project_roundtrip_verified"] = False
            _write_json(capability_path, capability)

            capability_sha256 = _sha256(capability_path)
            provenance["capability_snapshot"]["sha256"] = capability_sha256
            _write_json(provenance_path, provenance)

            run_path = root / RUN_RELATIVE
            run = _read_json(run_path)
            run["capability_snapshot_sha256"] = capability_sha256
            run["provenance_sha256"] = _sha256(provenance_path)
            _write_json(run_path, run)

            self.assertTrue(run_all._origin_multivariate_errors(root))

    def test_svg_loading_label_overlap_fails_after_artifact_hash_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _copy_minimal_origin_closure(root)
            self.assertEqual(run_all._origin_multivariate_errors(root), [])

            svg_relative = Path(
                "support/multivariate/q5_multivariate_structure.svg"
            )
            svg_path = root / svg_relative
            tree = ET.parse(svg_path)
            text_nodes = [
                element
                for element in tree.getroot().iter()
                if element.tag.rsplit("}", 1)[-1] == "text"
                and float(element.get("x", "-inf")) > 4000.0
            ]
            loading_labels = {
                "".join(element.itertext()).strip(): element for element in text_nodes
            }
            cos_label = loading_labels["cosT"]
            speed_label = loading_labels["v"]
            for coordinate in ("x", "y"):
                speed_label.set(coordinate, str(cos_label.get(coordinate)))
            for child in speed_label:
                if child.tag.rsplit("}", 1)[-1] == "tspan" and child.get("x"):
                    child.set("x", str(cos_label.get("x")))
            tree.write(svg_path, encoding="utf-8", xml_declaration=True)

            provenance_path = root / PROVENANCE_RELATIVE
            provenance = _read_json(provenance_path)
            provenance["artifacts"][svg_relative.as_posix()] = _sha256(svg_path)
            _write_json(provenance_path, provenance)

            run_path = root / RUN_RELATIVE
            run = _read_json(run_path)
            run["provenance_sha256"] = _sha256(provenance_path)
            _write_json(run_path, run)

            errors = run_all._origin_multivariate_errors(root)
            self.assertIn("artifact:svg-label-overlap", errors)


if __name__ == "__main__":
    unittest.main()
