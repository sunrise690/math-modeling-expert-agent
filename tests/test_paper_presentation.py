from __future__ import annotations

import unittest

from scripts.analyze_a_paper_presentation import (
    caption_inventory,
    extract_abstract_length,
    marker_counts,
    section_hits,
)


class PaperPresentationTests(unittest.TestCase):
    def test_extracts_bounded_abstract_length(self) -> None:
        text = "摘要：" + "本文建立可解释模型并给出量化结果。" * 8 + "关键词：优化；检验"
        length = extract_abstract_length(text)
        self.assertIsNotNone(length)
        self.assertGreater(length, 40)

    def test_detects_sections_and_argument_markers(self) -> None:
        text = "问题分析\n模型假设\n模型建立\n由于约束收紧，因此结果下降。由图可知该趋势稳定。"
        self.assertEqual(section_hits(text)[:3], ["问题分析", "模型假设", "模型建立"])
        counts = marker_counts(text)
        self.assertEqual(counts["因果解释"], 2)
        self.assertEqual(counts["图表解读"], 1)
        self.assertGreaterEqual(counts["结果落地"], 1)

    def test_counts_unique_informative_captions(self) -> None:
        text = "图 1 系统能量传递与状态变量关系\n正文\n图 1\n表 2 参数标定结果与实测误差\n"
        inventory = caption_inventory(text)
        self.assertEqual(inventory["figureCaptions"], 1)
        self.assertEqual(inventory["tableCaptions"], 1)
        self.assertEqual(inventory["informativeFigureCaptions"], 1)
        self.assertEqual(inventory["informativeTableCaptions"], 1)


if __name__ == "__main__":
    unittest.main()
