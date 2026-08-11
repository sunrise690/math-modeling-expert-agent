from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.ingest_reference_archives import IngestState, ingest_zip_bytes, portable_parts, safe_parts


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


class ReferenceArchiveTests(unittest.TestCase):
    def test_rejects_traversal_and_normalizes_windows_names(self) -> None:
        self.assertIsNone(safe_parts("../outside.txt"))
        self.assertIsNone(safe_parts("C:/outside.txt"))
        self.assertEqual(portable_parts(("code", "13-输出多个?.py")), ("code", "13-输出多个_.py"))

    def test_ingests_nested_readable_files_and_deduplicates(self) -> None:
        nested = make_zip({"solver.py": b"print('solve')", "ignored.exe": b"MZ"})
        outer = make_zip(
            {
                "notes/model.txt": b"force balance",
                "copy/model.txt": b"force balance",
                "nested.zip": nested,
                "../unsafe.txt": b"no",
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            state = IngestState(destination=Path(temp_dir))
            ingest_zip_bytes(outer, "reference", "reference.zip", state, 0)
            self.assertEqual(len(state.extracted), 2)
            self.assertEqual(len(state.duplicates), 1)
            self.assertEqual(state.skipped[".exe"], 1)
            self.assertEqual(state.skipped["unsafe-path"], 1)
            self.assertEqual(state.errors, [])
            self.assertTrue((Path(temp_dir) / "reference" / "notes" / "model.txt").is_file())
            self.assertTrue((Path(temp_dir) / "reference" / "nested" / "solver.py").is_file())


if __name__ == "__main__":
    unittest.main()
