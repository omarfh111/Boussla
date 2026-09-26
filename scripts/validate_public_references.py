"""Recheck official source response hashes without printing source content.

This requires network access. A changed source must be manually reinspected;
the script never updates the reviewed manifest automatically.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib

import httpx

from boussla.retrieval.corpus import load_public_references


def main() -> None:
    records = load_public_references()
    if not 24 <= len(records) <= 40:
        raise SystemExit("unexpected reviewed corpus size")
    sources: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.review_status != "REVIEWED":
            raise SystemExit("unreviewed record in public manifest")
        sources[record.source_url].add(record.source_hash)
    if len(sources) < 3 or any(len(hashes) != 1 for hashes in sources.values()):
        raise SystemExit("insufficient or inconsistent source provenance")
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for url, hashes in sources.items():
            response = client.get(url)
            response.raise_for_status()
            if hashlib.sha256(response.content).hexdigest() not in hashes:
                raise SystemExit("source content changed; inspect before any manifest update")
    print("reviewed_passages", len(records), "official_sources", len(sources), "hash_match", True)


if __name__ == "__main__":
    main()
