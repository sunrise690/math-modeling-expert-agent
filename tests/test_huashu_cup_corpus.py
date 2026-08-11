from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.analyze_huashu_cup_corpus import (
    analyze_image_color,
    infer_title,
    parse_identity,
    sanitize_strings,
    terminal_section_start,
)


class HuashuCupCorpusTests(unittest.TestCase):
    def test_parses_edition_problem_and_paper_number(self) -> None:
        root = Path("corpus")
        path = root / "第六届" / "B题优秀论文2.pdf"
        identity = parse_identity(path, root)
        self.assertEqual(identity["edition"], 6)
        self.assertEqual(identity["problem"], "B")
        self.assertEqual(identity["paperNumber"], 2)

    def test_infers_title_instead_of_participant_code(self) -> None:
        pages = [
            "所属类别\n2025 年华数杯\n研究生组 CM2501930\n"
            "多孔膜光反射性能的优化与控制\n摘要\n本文研究多孔膜。"
        ]
        self.assertEqual(infer_title(pages, "A题优秀论文1"), "多孔膜光反射性能的优化与控制")

    def test_color_profile_routes_blue_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "blue.png"
            Image.new("RGB", (100, 100), "#2F6B9A").save(path)
            profile = analyze_image_color(path)
        self.assertGreater(profile["chromaticRatio"], 0.9)
        self.assertGreater(profile["hueCounts"].get("蓝", 0), 0)

    def test_sanitizes_invalid_pdf_text_surrogates(self) -> None:
        payload = sanitize_strings({"caption": "角度\ud835路径"})
        self.assertEqual(payload["caption"], "角度?路径")

    def test_terminal_section_ignores_abstract_mentions(self) -> None:
        pages = ["摘要中提到附录数据", "问题分析", "模型建立", "8 参考文献", "附录 A"]
        self.assertEqual(terminal_section_start(pages), 4)

    def test_generated_reference_covers_all_papers_and_skill_routes_to_it(self) -> None:
        root = Path(__file__).resolve().parents[1]
        references = root / "skills" / "cumcm-expert-agent" / "references"
        payload = json.loads((references / "huashu-cup-corpus-index.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["summary"]["paperCount"], 18)
        self.assertEqual(payload["summary"]["pageCount"], 706)
        self.assertEqual(payload["summary"]["years"], [2023, 2024, 2025])
        self.assertTrue(all(paper["visualProfile"]["status"] == "ok" for paper in payload["papers"]))
        self.assertTrue(all("reviewFiles" not in paper["visualProfile"] for paper in payload["papers"]))
        skill = (root / "skills" / "cumcm-expert-agent" / "SKILL.md").read_text(encoding="utf-8")
        for name in (
            "huashu-cup-corpus-lessons.md",
            "huashu-cup-corpus-index.md",
            "huashu-cup-corpus-index.json",
            "huashu-cup-visual-writing-patterns.md",
        ):
            self.assertIn(name, skill)


if __name__ == "__main__":
    unittest.main()
