import hashlib
import json

from scripts.live_judge.pack import DOCUMENTS, PACK, pdf_bytes


def test_committed_documents_match_deterministic_generator():
    for filename, (style, lines) in DOCUMENTS.items():
        actual = (PACK / "documents" / filename).read_bytes()
        expected = pdf_bytes(*DOCUMENTS["invoice-fr.pdf"]) if style == "duplicate" else pdf_bytes(style, lines)
        assert actual == expected


def test_manifest_runtime_oracle_separation():
    manifest = json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["scenarios"]) == 54 and len(manifest["documents"]) == 30
    for document in manifest["documents"]:
        content = (PACK / document["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == document["sha256"]
    for path in manifest["scenarios"]:
        raw = (PACK / path).read_text(encoding="utf-8")
        assert "expected" not in raw and "evaluation_only" not in raw
        scenario = json.loads(raw)
        assert scenario["case_id"] != "CASE-BRICKS-001"
        assert (PACK / scenario["observed_file"]).exists()
