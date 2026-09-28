#!/usr/bin/env python3
"""Independent arithmetic and PDF checks for the midterm House study."""

from __future__ import annotations

import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "midterm_house_20260928" / "raw"
OUT = ROOT / "_out" / "midterm_house_20260928"


def values(filename, column):
    with (RAW / filename).open(encoding="utf-8-sig") as f:
        return [(date.fromisoformat(r["observation_date"]), Decimal(r[column])) for r in csv.DictReader(f) if r[column].strip()]


def main():
    analysis = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))
    series = {"dgs10": values("DGS10.csv", "DGS10"), "sp500": values("SP500.csv", "SP500")}
    checks = []
    for case in analysis["cases"]:
        event_date = date.fromisoformat(case["election_date"])
        for asset in ("dgs10", "sp500"):
            rows = series[asset]; lookup = dict(rows); future = [(d,v) for d,v in rows if d > event_date]
            for h in (1,7,15):
                d, end = future[h-1]; base = lookup[event_date]
                expected = (end-base)*100 if asset == "dgs10" else (end/base-1)*100
                observed = case[asset]["observations"][str(h)]
                assert observed["date"] == d.isoformat()
                assert Decimal(observed["metric"]) == expected
                checks.append(f"{case['year']}:{asset}:{h}")
    reader = PdfReader(OUT / "midterm_house_report.pdf")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) == 4
    for token in ("2018년", "2022년", "-61.0bp", "+6.6%", "관측 데이터만으로 원인 특정 불가"):
        assert token in text, token
    result = {"arithmetic_checks": len(checks), "pdf_pages": len(reader.pages), "required_text": "pass"}
    (OUT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
