#!/usr/bin/env python3
"""Download and fingerprint the public inputs for the midterm House study.

The downloaded files stay under ``data/`` and are intentionally excluded from
Git.  This makes the report reproducible without committing source snapshots or
font binaries to the repository.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "data" / "midterm_house_20260928"

SOURCES = {
    "raw/2018_election_statistics.pdf": "https://history.house.gov/Institution/Election-Statistics/2018election/",
    "raw/2022_election_statistics.pdf": "https://history.house.gov/Institution/Election-Statistics/2022election/",
    "raw/house_party_divisions.html": "https://history.house.gov/Institution/Party-Divisions/Party-Divisions/",
    "raw/DGS10.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd=2018-10-01&coed=2022-12-31",
    "raw/SP500.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500&cosd=2018-10-01&coed=2022-12-31",
    "fonts/NotoSansKR.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf",
}


def download(url: str, attempts: int = 4) -> bytes:
    # FRED's graph endpoint currently rejects generic scripted user agents but
    # serves the same public CSV to the standard curl identifier.
    request = Request(url, headers={"User-Agent": "curl/8.0"})
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=60) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                return response.read()
        except Exception:
            if attempt == attempts:
                raise
            time.sleep(2 ** (attempt - 1))
    raise AssertionError("unreachable")


def main() -> None:
    records = []
    for relative_path, url in SOURCES.items():
        payload = download(url)
        destination = STUDY / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        records.append({
            "path": relative_path,
            "url": url,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
        print(f"downloaded {relative_path} ({len(payload):,} bytes)")
    manifest = {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": records,
    }
    (STUDY / "source_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(STUDY / "source_manifest.json")


if __name__ == "__main__":
    main()
