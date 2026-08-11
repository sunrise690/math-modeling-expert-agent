from __future__ import annotations

import unittest
from pathlib import Path

from scripts.summarize_a_paper_corpus import (
    METHOD_TERMS,
    infer_title,
    needs_ocr,
    public_source_label,
    term_pages,
    write_utf8_lf,
)


class ReferenceCorpusTests(unittest.TestCase):
    def test_detects_low_density_text_as_ocr_candidate(self) -> None:
        self.assertTrue(needs_ocr(["", "少量文字", ""]))
        self.assertFalse(needs_ocr(["热传导方程与边界条件" * 80, "数值求解与结果分析" * 80]))

    def test_routes_method_families_to_physical_pages(self) -> None:
        pages = ["受力分析并建立动力学状态方程", "使用有限差分进行数值计算", "灵敏度分析"]
        hits = term_pages(pages, METHOD_TERMS)
        self.assertEqual(hits["机理与守恒"], [1])
        self.assertEqual(hits["数值计算"], [2])

    def test_infers_title_before_abstract_for_generic_code(self) -> None:
        first_page = "波浪能装置输出功率优化设计\n\n摘要\n本文研究波浪能装置。"
        self.assertEqual(infer_title(Path("A001.pdf"), first_page), "波浪能装置输出功率优化设计")

    def test_does_not_use_participant_filename_as_title(self) -> None:
        self.assertEqual(infer_title(Path("甲队员乙队员丙队员A.pdf"), "参赛队承诺书"), "未识别标题")

    def test_public_source_label_hides_original_filename(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "2023" / "A001_参赛者姓名.pdf"
            source.parent.mkdir()
            source.write_bytes(b"paper")
            label = public_source_label(source, root)
            self.assertRegex(label, r"^2023/paper-[0-9a-f]{12}\.pdf$")
            self.assertNotIn("参赛者", label)

    def test_generated_text_uses_lf_on_windows(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "index.json"
            write_utf8_lf(output, "{\n  \"ok\": true\n}\n")
            self.assertNotIn(b"\r\n", output.read_bytes())


if __name__ == "__main__":
    unittest.main()
