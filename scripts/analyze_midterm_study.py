#!/usr/bin/env python3
"""Analyze post-midterm paths for opposition congressional majority flips."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "midterm_20260928" / "raw"
OUT = ROOT / "_out" / "midterm_20260928"
HORIZONS = (1, 7, 15)
EVENTS = (
    {"year": 2018, "election_date": "2018-11-06", "anchor": "2018-11-07",
     "president_party": "공화당", "winner": "민주당", "chamber": "하원",
     "before": "공화 241 / 민주 194", "after": "민주 235 / 공화 199"},
    {"year": 2022, "election_date": "2022-11-08", "anchor": "2022-11-09",
     "president_party": "민주당", "winner": "공화당", "chamber": "하원",
     "before": "민주 222 / 공화 212", "after": "공화 222 / 민주 213"},
)


def load_series(name: str) -> pd.Series:
    frame = pd.read_csv(RAW / f"{name}.csv", na_values=".")
    frame["observation_date"] = pd.to_datetime(frame["observation_date"])
    return frame.set_index("observation_date")[name].dropna().astype(float).sort_index()


def max_drawdown(values: pd.Series) -> float:
    return float((values / values.cummax() - 1).min() * 100)


def compute() -> dict:
    sp = load_series("SP500")
    y10 = load_series("DGS10")
    trading_dates = sp.index
    cases = []
    for event in EVENTS:
        anchor = pd.Timestamp(event["anchor"])
        pos = trading_dates.get_loc(anchor)
        row = dict(event)
        row["sp_anchor"] = float(sp.loc[anchor])
        row["yield_anchor"] = float(y10.loc[anchor])
        row["sp_returns"] = {}
        row["yield_changes_bp"] = {}
        row["target_dates"] = {}
        for h in HORIZONS:
            target = trading_dates[pos + h]
            row["target_dates"][str(h)] = target.date().isoformat()
            row["sp_returns"][str(h)] = float((sp.loc[target] / sp.loc[anchor] - 1) * 100)
            row["yield_changes_bp"][str(h)] = float((y10.loc[target] - y10.loc[anchor]) * 100)
        path = sp.iloc[pos:pos + max(HORIZONS) + 1]
        row["sp_mdd_15"] = max_drawdown(path)
        yield_path = y10.reindex(path.index).dropna()
        row["yield_min_change_bp_15"] = float((yield_path.min() - y10.loc[anchor]) * 100)
        row["yield_max_change_bp_15"] = float((yield_path.max() - y10.loc[anchor]) * 100)
        cases.append(row)

    baseline = {"range": [trading_dates.min().date().isoformat(), trading_dates.max().date().isoformat()]}
    for asset in ("sp500", "dgs10"):
        stats = {}
        for h in HORIZONS:
            vals = []
            for i in range(len(trading_dates) - h):
                start, target = trading_dates[i], trading_dates[i + h]
                if asset == "sp500":
                    vals.append((sp.loc[target] / sp.loc[start] - 1) * 100)
                elif start in y10.index and target in y10.index:
                    vals.append((y10.loc[target] - y10.loc[start]) * 100)
            s = pd.Series(vals, dtype=float)
            stats[str(h)] = {"n": int(s.count()), "mean": float(s.mean()),
                             "median": float(s.median()), "positive_pct": float((s > 0).mean() * 100)}
        baseline[asset] = stats

    metadata = {
        "definition": "2015년 이후 정기 중간선거에서 대통령 야당이 하원 또는 상원 다수당을 새로 획득",
        "anchor": "선거 다음 S&P 500 거래일 종가",
        "horizons": list(HORIZONS),
        "sp500": "FRED SP500, 배당 제외 가격지수",
        "dgs10": "FRED DGS10, 금리 수준 차이 × 100bp",
        "as_of": "2026-09-28",
        "sample_note": "2026년 중간선거는 분석일 현재 미실시이므로 2018·2022년 전체 확정 사례 2건",
    }
    sources = {
        "house_115": "https://history.house.gov/Congressional-Overview/Profiles/115th/",
        "house_116": "https://history.house.gov/Congressional-Overview/Profiles/116th/",
        "house_117": "https://history.house.gov/Congressional-Overview/Profiles/117th/",
        "house_118": "https://history.house.gov/Congressional-Overview/Profiles/118th/",
        "elections": "https://history.house.gov/Institution/Election-Statistics/Election-Statistics/",
        "sp500": "https://fred.stlouisfed.org/series/SP500",
        "dgs10": "https://fred.stlouisfed.org/series/DGS10",
    }
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.glob("*")) if p.is_file()}
    return {"metadata": metadata, "events": cases, "baseline": baseline, "sources": sources, "raw_sha256": hashes}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = compute()
    (OUT / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for e in result["events"]:
        for h in HORIZONS:
            rows.append({"year": e["year"], "anchor": e["anchor"], "horizon": h,
                         "target": e["target_dates"][str(h)], "sp500_return_pct": e["sp_returns"][str(h)],
                         "dgs10_change_bp": e["yield_changes_bp"][str(h)]})
    pd.DataFrame(rows).to_csv(OUT / "event_returns.csv", index=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
