from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_base import KnowledgeBase, KnowledgeError


def write_text_pdf(path: Path, text: str) -> None:
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
    )
    stream = DecodedStreamObject()
    safe_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({safe_text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as handle:
        writer.write(handle)


class KnowledgeBaseTests(unittest.TestCase):
    def test_normalizes_malformed_pdf_surrogates(self) -> None:
        normalized = KnowledgeBase._normalize_text("目标函数\ud835与约束")
        self.assertEqual(normalized, "目标函数�与约束")
        normalized.encode("utf-8")

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.materials = self.root / "materials"
        self.materials.mkdir()
        self.database = self.root / "knowledge.db"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_indexes_chinese_text_and_reads_grounded_chunk(self) -> None:
        (self.materials / "优化方法.md").write_text(
            "# 优化方法\n\n线性规划适用于目标函数与约束均为线性的情形。整数规划要求部分变量取整数。",
            encoding="utf-8",
        )
        knowledge = KnowledgeBase(self.database, [self.materials])
        summary = knowledge.reindex()
        self.assertEqual(summary["indexed"], 1)

        search = knowledge.search("线性规划", limit=3)
        self.assertEqual(search["count"], 1)
        hit = search["results"][0]
        self.assertEqual(hit["name"], "优化方法.md")
        self.assertIn("线性规划", hit["excerpt"])

        read = knowledge.read(hit["documentId"], hit["chunkId"])
        self.assertNotIn("path", read["document"])
        self.assertNotIn(str(self.root), str(read))
        self.assertIn("整数规划", read["content"][0]["text"])

    def test_indexes_python_and_matlab_reference_code(self) -> None:
        (self.materials / "solve_transport.py").write_text(
            "# 运输规划\nobjective = 'minimum transport cost'\n",
            encoding="utf-8",
        )
        (self.materials / "heat_equation.m").write_text(
            "% 热传导有限差分\ntemperature = zeros(10, 10);\n",
            encoding="utf-8",
        )
        knowledge = KnowledgeBase(self.database, [self.materials])
        summary = knowledge.reindex()
        self.assertEqual(summary["indexed"], 2)
        self.assertEqual(knowledge.search("transport cost")["results"][0]["name"], "solve_transport.py")
        self.assertEqual(knowledge.search("热传导有限差分")["results"][0]["name"], "heat_equation.m")

    def test_pdf_search_keeps_page_location(self) -> None:
        pdf_path = self.materials / "robust.pdf"
        write_text_pdf(pdf_path, "robust optimization sensitivity analysis")
        knowledge = KnowledgeBase(self.database, [self.materials])
        summary = knowledge.reindex()
        self.assertEqual(summary["indexed"], 1)

        result = knowledge.search("sensitivity analysis")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["location"], "第 1 页")

    def test_reindex_is_incremental_and_removes_deleted_files(self) -> None:
        text_path = self.materials / "a.txt"
        pdf_path = self.materials / "b.pdf"
        text_path.write_text("simulation queue model", encoding="utf-8")
        write_text_pdf(pdf_path, "network shortest path")
        knowledge = KnowledgeBase(self.database, [self.materials])
        first = knowledge.reindex()
        self.assertEqual(first["indexed"], 2)

        second = knowledge.reindex()
        self.assertEqual(second["unchanged"], 2)
        self.assertEqual(second["indexed"], 0)

        text_path.write_text("simulation queue model and discrete events", encoding="utf-8")
        pdf_path.unlink()
        third = knowledge.reindex()
        self.assertEqual(third["indexed"], 1)
        self.assertEqual(third["removed"], 1)
        self.assertEqual(knowledge.status()["documents"], 1)

    def test_deduplicates_identical_content(self) -> None:
        (self.materials / "first.md").write_text("multi objective optimization", encoding="utf-8")
        (self.materials / "second.md").write_text("multi objective optimization", encoding="utf-8")
        knowledge = KnowledgeBase(self.database, [self.materials])
        summary = knowledge.reindex()
        self.assertEqual(summary["indexed"], 1)
        self.assertEqual(summary["duplicates"], 1)
        self.assertEqual(summary["status"]["duplicateDocuments"], 1)
        self.assertEqual(knowledge.search("objective optimization")["count"], 1)

    def test_excludes_spreadsheets_likely_to_contain_personal_information(self) -> None:
        import pandas as pd

        sensitive_path = self.materials / "参赛信息汇总.xlsx"
        pd.DataFrame({"姓名": ["张三"], "电话": ["13800000000"]}).to_excel(sensitive_path, index=False)
        knowledge = KnowledgeBase(self.database, [self.materials])
        summary = knowledge.reindex()
        self.assertEqual(summary["excluded"], 1)
        self.assertEqual(summary["status"]["excludedDocuments"], 1)
        self.assertEqual(knowledge.search("张三")["count"], 0)

    def test_rejects_invalid_document_identifier(self) -> None:
        knowledge = KnowledgeBase(self.database, [self.materials])
        with self.assertRaises(KnowledgeError):
            knowledge.read("../secret")


if __name__ == "__main__":
    unittest.main()
