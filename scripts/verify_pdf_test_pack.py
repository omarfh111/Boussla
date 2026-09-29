"""Check generated PDFs before manual upload; never load answer keys at runtime."""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from boussla.contracts import DocumentText, PageText
from boussla.documents.labelled import classify_native


def verify(folder: Path) -> None:
    manifest = json.loads((folder / "evaluation_only" / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest) == 24
    existing_hashes = {
        sha256(path.read_bytes()).hexdigest()
        for path in (ROOT / "docs" / "build_lock" / "fixtures" / "documents").glob("*.pdf")
    }
    for item in manifest:
        data = (folder / item["file"]).read_bytes()
        assert data.startswith(b"%PDF-")
        assert sha256(data).hexdigest() not in existing_hashes, item["file"]
        reader = PdfReader(BytesIO(data), strict=True)
        if item["file"].startswith("cas_24"):
            assert reader.is_encrypted
            assert reader.decrypt("synthetic-test-only")
        else:
            assert not reader.is_encrypted
        assert len(reader.pages) == item["pages"]
        if item["file"].startswith("cas_24"):
            continue
        pages = tuple(PageText(page=i, text=page.extract_text() or "") for i, page in enumerate(reader.pages, 1))
        readable = any(page.text.strip() for page in pages)
        assert readable == item["native_text_expected"], item["file"]
        document_text = DocumentText(
            document_id=item["file"], pages=pages,
            status="OK" if readable else "UNSUPPORTED",
        )
        assert classify_native(document_text).value == item["expected_native_router_class"], item["file"]
    print(f"PASS: {len(manifest)} valid, new synthetic PDFs; pages, text, and routing checked")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "folder", nargs="?", type=Path,
        default=ROOT / "output" / "pdf" / "boussla_tests_2026-09-29",
    )
    verify(parser.parse_args().folder)
