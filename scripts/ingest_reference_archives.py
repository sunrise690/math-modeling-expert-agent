from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


READABLE_EXTENSIONS = {
    ".bib",
    ".bst",
    ".cls",
    ".csv",
    ".docx",
    ".json",
    ".m",
    ".md",
    ".pdf",
    ".py",
    ".tex",
    ".tsv",
    ".txt",
    ".xlsx",
}
ARCHIVE_EXTENSIONS = {".rar", ".zip"}
MAX_NESTING_DEPTH = 4
MAX_MEMBER_BYTES = 100 * 1024 * 1024
WINDOWS_RESERVED_NAMES = {
    "aux",
    "con",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_parts(name: str) -> tuple[str, ...] | None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if any(":" in part for part in path.parts):
        return None
    return tuple(path.parts)


def portable_parts(parts: tuple[str, ...]) -> tuple[str, ...]:
    translated: list[str] = []
    invalid = '<>:"/\\|?*'
    table = str.maketrans({character: "_" for character in invalid})
    for part in parts:
        cleaned = part.translate(table).rstrip(" .") or "_"
        if cleaned.casefold() in WINDOWS_RESERVED_NAMES:
            cleaned = f"_{cleaned}"
        if len(cleaned) > 160:
            suffix = Path(cleaned).suffix
            stem = Path(cleaned).stem[:120]
            cleaned = f"{stem}-{hashlib.sha256(part.encode('utf-8')).hexdigest()[:12]}{suffix}"
        translated.append(cleaned)
    return tuple(translated)


def decode_listing(data: bytes) -> str:
    for encoding in ("utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


@dataclass
class IngestState:
    destination: Path
    extracted: list[dict[str, object]] = field(default_factory=list)
    duplicates: list[dict[str, str]] = field(default_factory=list)
    skipped: Counter[str] = field(default_factory=Counter)
    warnings: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    content_owners: dict[str, str] = field(default_factory=dict)

    def store(self, logical_name: str, data: bytes, source_archive: str) -> None:
        parts = safe_parts(logical_name)
        if not parts:
            self.skipped["unsafe-path"] += 1
            return
        if not data:
            self.skipped["empty"] += 1
            return
        if len(data) > MAX_MEMBER_BYTES:
            self.skipped["oversized"] += 1
            return
        digest = sha256_bytes(data)
        relative = Path(*portable_parts(parts))
        relative_key = relative.as_posix()
        owner = self.content_owners.get(digest)
        if owner:
            self.duplicates.append({"path": relative_key, "duplicateOf": owner, "sha256": digest})
            return
        target = self.destination / relative
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError as error:
            self.errors.append({"archive": source_archive, "member": logical_name, "error": str(error)})
            return
        self.content_owners[digest] = relative_key
        self.extracted.append(
            {
                "path": relative_key,
                "extension": target.suffix.lower(),
                "size": len(data),
                "sha256": digest,
                "sourceArchive": source_archive,
                **({"logicalPath": logical_name} if logical_name != relative_key else {}),
            }
        )


def ingest_zip_bytes(
    data: bytes,
    prefix: str,
    archive_label: str,
    state: IngestState,
    depth: int,
) -> None:
    if depth > MAX_NESTING_DEPTH:
        state.skipped["nesting-depth"] += 1
        return
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                parts = safe_parts(entry.filename)
                if not parts:
                    state.skipped["unsafe-path"] += 1
                    continue
                if entry.file_size > MAX_MEMBER_BYTES:
                    state.skipped["oversized"] += 1
                    continue
                logical_name = "/".join(part for part in (prefix, *parts) if part)
                extension = Path(parts[-1]).suffix.lower()
                if extension not in READABLE_EXTENSIONS | ARCHIVE_EXTENSIONS:
                    state.skipped[extension or "no-extension"] += 1
                    continue
                member_data = archive.read(entry)
                if extension == ".zip":
                    ingest_zip_bytes(member_data, logical_name.removesuffix(".zip"), logical_name, state, depth + 1)
                elif extension == ".rar":
                    ingest_rar_bytes(member_data, logical_name.removesuffix(".rar"), logical_name, state, depth + 1)
                else:
                    state.store(logical_name, member_data, archive_label)
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        state.errors.append({"archive": archive_label, "error": str(error)})


def ingest_rar_bytes(
    data: bytes,
    prefix: str,
    archive_label: str,
    state: IngestState,
    depth: int,
) -> None:
    if depth > MAX_NESTING_DEPTH:
        state.skipped["nesting-depth"] += 1
        return
    tar = shutil.which("tar")
    if not tar:
        state.errors.append({"archive": archive_label, "error": "tar command not found; RAR skipped"})
        return
    with tempfile.TemporaryDirectory(prefix="modeling-rar-") as temp_dir:
        rar_path = Path(temp_dir) / "source.rar"
        rar_path.write_bytes(data)
        listing = subprocess.run([tar, "-tf", str(rar_path)], capture_output=True, check=False)
        if listing.returncode != 0:
            state.errors.append(
                {"archive": archive_label, "error": decode_listing(listing.stderr).strip() or "RAR listing failed"}
            )
            return
        for raw_name in decode_listing(listing.stdout).splitlines():
            name = raw_name.strip()
            parts = safe_parts(name)
            if not parts or name.endswith(("/", "\\")):
                if name and not parts:
                    state.skipped["unsafe-path"] += 1
                continue
            logical_name = "/".join(part for part in (prefix, *parts) if part)
            extension = Path(parts[-1]).suffix.lower()
            if extension not in READABLE_EXTENSIONS | ARCHIVE_EXTENSIONS:
                state.skipped[extension or "no-extension"] += 1
                continue
            extracted = subprocess.run([tar, "-xOf", str(rar_path), name], capture_output=True, check=False)
            if extracted.returncode != 0:
                state.warnings.append(
                    {
                        "archive": archive_label,
                        "member": name,
                        "error": decode_listing(extracted.stderr).strip() or "RAR member extraction failed",
                    }
                )
                state.skipped["rar-member-unreadable"] += 1
                continue
            if len(extracted.stdout) > MAX_MEMBER_BYTES:
                state.skipped["oversized"] += 1
                continue
            if extension == ".zip":
                ingest_zip_bytes(
                    extracted.stdout,
                    logical_name.removesuffix(".zip"),
                    logical_name,
                    state,
                    depth + 1,
                )
            elif extension == ".rar":
                ingest_rar_bytes(
                    extracted.stdout,
                    logical_name.removesuffix(".rar"),
                    logical_name,
                    state,
                    depth + 1,
                )
            else:
                state.store(logical_name, extracted.stdout, archive_label)


def ingest_archive(path: Path, state: IngestState) -> dict[str, object]:
    data = path.read_bytes()
    record = {"name": path.name, "size": len(data), "sha256": sha256_bytes(data)}
    if path.suffix.lower() == ".zip":
        ingest_zip_bytes(data, path.stem, path.name, state, 0)
    elif path.suffix.lower() == ".rar":
        ingest_rar_bytes(data, path.stem, path.name, state, 0)
    else:
        raise ValueError(f"Unsupported archive: {path}")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely ingest readable modeling references from ZIP/RAR archives.")
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    state = IngestState(destination=destination)
    sources = []
    for archive in args.archives:
        resolved = archive.expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        sources.append(ingest_archive(resolved, state))

    manifest = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "destination": destination.name,
        "extractedCount": len(state.extracted),
        "duplicateCount": len(state.duplicates),
        "skipped": dict(sorted(state.skipped.items())),
        "warningCount": len(state.warnings),
        "errorCount": len(state.errors),
        "files": state.extracted,
        "duplicates": state.duplicates,
        "warnings": state.warnings,
        "errors": state.errors,
    }
    manifest_path = args.manifest.resolve() if args.manifest else destination / "ingest-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in ("extractedCount", "duplicateCount", "skipped", "warningCount", "errorCount")
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(f"Manifest: {manifest_path}")
    return 0 if not state.errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
