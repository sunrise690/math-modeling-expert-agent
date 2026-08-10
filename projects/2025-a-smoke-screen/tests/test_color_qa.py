from __future__ import annotations

import json
import math
import re
import statistics
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MATLAB_DIR = PROJECT_ROOT / "src" / "matlab"
REPO_ROOT = PROJECT_ROOT.parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import generate_figures  # noqa: E402


def _rgb(code: str) -> tuple[float, float, float]:
    code = code.removeprefix("#")
    return tuple(int(code[index : index + 2], 16) / 255 for index in (0, 2, 4))


def _linear_channel(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _luminance(code: str) -> float:
    red, green, blue = (_linear_channel(value) for value in _rgb(code))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(first: str, second: str) -> float:
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _lab(code: str) -> tuple[float, float, float]:
    red, green, blue = (_linear_channel(value) for value in _rgb(code))
    x = (0.4124564 * red + 0.3575761 * green + 0.1804375 * blue) / 0.95047
    y = 0.2126729 * red + 0.7151522 * green + 0.0721750 * blue
    z = (0.0193339 * red + 0.1191920 * green + 0.9503041 * blue) / 1.08883

    def transform(value: float) -> float:
        delta = 6 / 29
        if value > delta**3:
            return value ** (1 / 3)
        return value / (3 * delta**2) + 4 / 29

    fx, fy, fz = transform(x), transform(y), transform(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


class ColorQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = json.loads(
            (MATLAB_DIR / "palette_spec.json").read_text(encoding="utf-8")
        )

    def test_palette_semantics_and_contrast(self) -> None:
        roles = self.spec["roles"]
        constraints = self.spec["constraints"]
        self.assertEqual(roles["paper"], "#FFFFFF")
        self.assertIn("negative quantities only", self.spec["semantics"]["clay"])
        for role in ("ink", "muted", "secondary", "primary", "clay", "risk"):
            with self.subTest(role=role):
                self.assertGreaterEqual(
                    _contrast(roles[role], roles["paper"]),
                    constraints["minimum_text_contrast_on_paper"],
                )
        self.assertLessEqual(
            _contrast(roles["grid"], roles["paper"]),
            constraints["maximum_grid_contrast_on_paper"],
        )

    def test_sequential_map_is_monotone_and_not_visually_lumpy(self) -> None:
        labs = [_lab(code) for code in self.spec["sequential"]]
        lightness = [lab[0] for lab in labs]
        self.assertTrue(all(a > b for a, b in zip(lightness, lightness[1:])))
        self.assertGreaterEqual(lightness[0] - lightness[-1], 50)
        delta_e = [
            math.dist(first, second) for first, second in zip(labs, labs[1:])
        ]
        self.assertLessEqual(
            statistics.pstdev(delta_e) / statistics.fmean(delta_e), 0.45
        )

    def test_renderers_use_one_palette_source(self) -> None:
        forbidden = re.compile(r"\b(?:jet|rainbow|hsv|turbo)\s*\(", re.IGNORECASE)
        hex_literal = re.compile(r"#[0-9A-Fa-f]{6}")
        for path in sorted(MATLAB_DIR.glob("render_*.m")):
            source = path.read_text(encoding="utf-8")
            with self.subTest(renderer=path.name):
                self.assertIn("contest_palette()", source)
                self.assertIsNone(hex_literal.search(source))
                self.assertIsNone(forbidden.search(source))

    def test_palette_files_are_bound_into_figure_provenance(self) -> None:
        provenance = generate_figures._dependency_provenance()
        sources = set(provenance["sources_sha256"])
        self.assertIn("src/matlab/contest_palette.m", sources)
        self.assertIn("src/matlab/palette_spec.json", sources)

    def test_reusable_agent_theme_matches_project_palette(self) -> None:
        theme = (
            REPO_ROOT
            / "skills"
            / "cumcm-expert-agent"
            / "assets"
            / "matlab"
            / "contest_figure_theme.m"
        ).read_text(encoding="utf-8")
        expected = {
            "paper": "#FFFFFF",
            "ink": "#252A30",
            "muted": "#687078",
            "secondary": "#6D767E",
            "grid": "#E6EAED",
            "primary": "#3F6688",
            "accentWarm": "#AD5D45",
            "accentRisk": "#76536B",
        }
        for name, code in expected.items():
            with self.subTest(name=name):
                self.assertRegex(
                    theme,
                    rf"T\.{re.escape(name)}\s*=\s*hexrgb\('{re.escape(code)}'\)",
                )


if __name__ == "__main__":
    unittest.main()
