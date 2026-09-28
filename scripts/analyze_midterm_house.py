#!/usr/bin/env python3
"""Calculate post-election DGS10 changes and S&P 500 price returns.

The study universe is the regular U.S. midterm elections after 2015.  Event
classification is intentionally explicit rather than inferred from market data.
Raw inputs are downloaded separately and are never overwritten by this script.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "midterm_house_20260928" / "raw"
OUT = ROOT / "_out" / "midterm_house_20260928"
HORIZONS = (1, 7, 15)
EVENTS = (
    {"year": 2018, "election_date": "2018-11-06", "president_party": "Republican", "winner": "Democratic", "house_seats": "235–199"},
    {"year": 2022, "election_date": "2022-11-08", "president_party": "Democratic", "winner": "Republican", "house_seats": "222–213"},
)


def load_series(path: Path, column: str) -> list[tuple[date, Decimal]]:
    rows: list[tuple[date, Decimal]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = row[column].strip()
            if value not in {"", "."}:
                rows.append((date.fromisoformat(row["observation_date"]), Decimal(value)))
    if not rows or any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError(f"Series is empty, duplicated, or unsorted: {path}")
    return rows


def event_path(series: list[tuple[date, Decimal]], event_date: date, kind: str) -> dict:
    lookup = {d: v for d, v in series}
    if event_date not in lookup:
        raise ValueError(f"Missing event-date value: {event_date}")
    future = [(d, v) for d, v in series if d > event_date]
    base = lookup[event_date]
    result = {"base_date": event_date.isoformat(), "base_value": str(base), "observations": {}}
    for horizon in HORIZONS:
        d, value = future[horizon - 1]
        metric = (value - base) * 100 if kind == "yield" else (value / base - 1) * 100
        result["observations"][str(horizon)] = {
            "date": d.isoformat(), "value": str(value), "metric": str(metric)
        }
    return result


def baseline(series: list[tuple[date, Decimal]], kind: str) -> dict:
    """Overlapping rolling observations over the requested study interval."""
    values = [v for d, v in series if date(2018, 11, 6) <= d <= date(2022, 11, 30)]
    out = {}
    for horizon in HORIZONS:
        metrics = []
        for i in range(len(values) - horizon):
            a, b = values[i], values[i + horizon]
            metrics.append((b - a) * 100 if kind == "yield" else (b / a - 1) * 100)
        ordered = sorted(metrics)
        n = len(metrics)
        median = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2
        out[str(horizon)] = {
            "n": n,
            "mean": str(sum(metrics) / n),
            "median": str(median),
            "positive_pct": str(Decimal(100) * sum(x > 0 for x in metrics) / n),
        }
    return out


def q(value: Decimal, places: str = "0.1") -> str:
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def build_analysis(dgs: list[tuple[date, Decimal]], spx: list[tuple[date, Decimal]]) -> dict:
    cases = []
    for event in EVENTS:
        election_date = date.fromisoformat(event["election_date"])
        cases.append({**event, "dgs10": event_path(dgs, election_date, "yield"), "sp500": event_path(spx, election_date, "price")})
    summaries = {}
    for asset in ("dgs10", "sp500"):
        summaries[asset] = {}
        for horizon in HORIZONS:
            vals = [Decimal(case[asset]["observations"][str(horizon)]["metric"]) for case in cases]
            summaries[asset][str(horizon)] = {
                "n": len(vals), "mean": q(sum(vals) / len(vals)),
                "median": q(sum(vals) / len(vals)),
                "positive_pct": q(Decimal(100) * sum(v > 0 for v in vals) / len(vals)),
            }
    return {
        "definition": {
            "universe": "Regular U.S. midterm elections from 2015 through 2022",
            "event": "The president's opposition party takes House majority control from the president's party",
            "base": "Election-day close/value; next valid observation is horizon 1",
            "dgs10": "DGS10 percentage-point yield multiplied by 100; change in basis points",
            "sp500": "SP500 price-index percentage return; dividends excluded",
        },
        "cases": cases, "summary": summaries,
        "baseline": {"dgs10": baseline(dgs, "yield"), "sp500": baseline(spx, "price")},
    }


def main() -> None:
    dgs = load_series(DATA / "DGS10.csv", "DGS10")
    spx = load_series(DATA / "SP500.csv", "SP500")
    analysis = build_analysis(dgs, spx)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUT / "analysis.json")


if __name__ == "__main__":
    main()
