import unittest

from scripts.audit_paper import (
    _count_equations,
    _count_figure_interpretations,
    _count_figures,
    _plain_text,
    _question_blocks,
    _question_index,
    _section_blocks,
    audit,
)


class PaperAuditPdfTextTests(unittest.TestCase):
    def test_numbered_pdf_question_headings_keep_full_blocks(self) -> None:
        source = """
1 问题分析与技术路线
总体路线说明。
5 问题一：给定策略的连续复算
第一问模型、算法、结果与检验。
5.1 模型检验与小结
第一问的连续边界残差与独立回算。
6 问题二：单机单弹连续优化
第二问模型、算法、结果与检验。
7 问题三：区间协同
第三问模型、算法、结果与检验。
8 问题四：时间互补
第四问模型、算法、结果与检验。
9 问题五：分层优化
第五问模型、算法、结果与检验。
11 模型评价、适用边界与改进
局限性说明。
参考文献
[1] Reference.
"""
        blocks = _section_blocks(source, ".pdf")
        indexed = {_question_index(title): body for title, body in blocks if _question_index(title)}
        self.assertEqual(set(indexed), {1, 2, 3, 4, 5})
        self.assertIn("第一问模型", indexed[1])
        self.assertNotIn("第二问模型", indexed[1])
        question_blocks = _question_blocks(source, ".pdf")
        question_bodies = {_question_index(title): body for title, body in question_blocks}
        self.assertIn("连续边界残差", question_bodies[1])
        self.assertNotIn("第二问模型", question_bodies[1])

    def test_pdf_equation_numbers_are_counted_once(self) -> None:
        source = "目标函数。                                      (1)\n约束。 (2)\n正文引用式 (1)。\n"
        self.assertEqual(_count_equations(source, ".pdf"), 2)

    def test_pdf_figure_references_are_deduplicated_by_number(self) -> None:
        source = """
图 1 给出简短引用。
图 1 Q1 连续区间及其边界误差，零线对应进入与退出事件。
图 2 Q2 多种子稳定性。
图 2 显示结果一致。
"""
        count, captions = _count_figures(source, ".pdf", {})
        self.assertEqual(count, 2)
        self.assertTrue(any("Q1 连续区间" in caption for caption in captions))
        self.assertEqual(_count_figure_interpretations(source, ".pdf", captions, count), 1)

    def test_tex_escaped_percent_is_not_treated_as_comment(self) -> None:
        source = "result 95\\% remains % real comment\nnext line"
        plain = _plain_text(source, ".tex")
        self.assertIn("95% remains", plain)
        self.assertNotIn("real comment", plain)
        self.assertIn("next line", plain)

    def test_figures_inherit_their_question_section(self) -> None:
        source = r"""
\section{问题一：轨迹模型}
\begin{figure}\caption{轨迹与遮蔽区间}\label{fig:first}\end{figure}
\section{问题二：稳健优化}
\begin{figure}\caption{参数扰动结果}\label{fig:second}\end{figure}
"""
        result = audit(source, ".tex", {}, expected_questions=2, full_paper=False)
        self.assertEqual(result["metrics"]["figuresByQuestion"], {"1": 1, "2": 1})
        self.assertEqual(result["metrics"]["questionsWithoutFigure"], [])

    def test_interpretation_requires_a_bound_figure_reference(self) -> None:
        source = """
图 1 轨迹与遮蔽区间
图 2 参数扰动结果
模型结果表明方案稳定，但这里没有引用任何图。
如图 1 所示，曲线显示误差随步长下降。
"""
        count, captions = _count_figures(source, ".pdf", {})
        self.assertEqual(count, 2)
        self.assertEqual(_count_figure_interpretations(source, ".pdf", captions, count), 1)

    def test_pdf_bibliography_entries_do_not_count_as_body_citations(self) -> None:
        references = "\n".join(f"[{index}] Reference {index}." for index in range(1, 7))
        source = f"正文没有数字引用。\n参考文献\n{references}\n"
        result = audit(source, ".pdf", {}, expected_questions=1, full_paper=False)
        self.assertEqual(result["metrics"]["citations"], 0)
        self.assertEqual(result["metrics"]["bibliographyItems"], 6)
        gate = next(item for item in result["gates"] if item["id"] == "scholarly_traceability")
        self.assertFalse(gate["passed"])

    def test_validation_gate_requires_numeric_diagnostics(self) -> None:
        source = """
图 1 Q1 敏感性验证
图 2 Q2 误差检验
验证、稳健性、鲁棒性、残差、误差、收敛、回算、对照、基线均已讨论。
"""
        hollow = audit(source, ".pdf", {}, expected_questions=2, full_paper=False)
        hollow_gate = next(item for item in hollow["gates"] if item["id"] == "validation_traceability")
        self.assertFalse(hollow_gate["passed"])
        numeric = audit(
            source + "\n最大残差为 1.2e-6 m，步长误差为 0.03 s。\n",
            ".pdf",
            {},
            expected_questions=2,
            full_paper=False,
        )
        numeric_gate = next(item for item in numeric["gates"] if item["id"] == "validation_traceability")
        self.assertTrue(numeric_gate["passed"])
        self.assertGreaterEqual(numeric["metrics"]["validationNumericSignals"], 2)


if __name__ == "__main__":
    unittest.main()
