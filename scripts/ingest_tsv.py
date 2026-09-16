# -*- coding: utf-8 -*-
"""Investing.com 지표 페이지에서 받아온 원문 TSV -> 이벤트 CSV.

원문(data/raw/*.tsv)은 그대로 보존하고 정제본만 data/events/ 에 쓴다.
컬럼: occurrence_time(UTC) | reference_period | actual | forecast | previous | unit

실행: py -3 scripts/ingest_tsv.py
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import datetime as dt
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
EVENTS = os.path.join(ROOT, "data", "events")
os.makedirs(EVENTS, exist_ok=True)

SPEC = {
    "us_core_cpi": ("US_CORE_CPI", "core_MoM"),
    "us_nfp":      ("US_NFP",      "headline"),
    "us_ism_mfg":  ("US_ISM_MFG",  "headline"),
}
MON = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

PULLED = "2026-08-30"   # 확정일. 과거 행은 재조회하지 않는다.


def ref_month(rel, abbr):
    """참조월 = 표기된 월. 표기월이 발표월보다 크면 전년으로 넘긴다."""
    rm = MON[abbr]
    ry = rel.year if rm <= rel.month else rel.year - 1
    return "%04d-%02d" % (ry, rm)


def run(name):
    indicator, variant = SPEC[name]
    rows, skipped = [], []
    path = os.path.join(RAW, name + ".tsv")
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            if len(p) < 6:
                skipped.append((ln, "열 부족", line.strip()[:50]))
                continue
            rel = dt.datetime.strptime(p[0], "%Y-%m-%dT%H:%M:%SZ").date()
            act, fc, prev, unit = p[2].strip(), p[3].strip(), p[4].strip(), p[5].strip()
            if act == "":
                skipped.append((ln, "미발표(actual 없음)", p[0] + " " + p[1]))
                continue
            notes = "" if fc != "" else "forecast 미기재"
            rows.append([rel.isoformat(), indicator, variant, act, fc, prev,
                         unit, PULLED, notes, ref_month(rel, p[1].strip())])

    rows.sort(key=lambda r: (r[0], r[9]))
    out = os.path.join(EVENTS, name + ".csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write("release_date,indicator,variant,actual,forecast,previous,"
                "unit,pulled_on,notes,ref_month\n")
        for r in rows:
            f.write(",".join(r) + "\n")

    nf = sum(1 for r in rows if r[4] == "")
    dup = len(rows) - len(set(r[9] for r in rows))
    print("%-12s n=%-3d %s ~ %s  참조월 %s~%s  forecast결측=%d  참조월중복=%d" % (
        name, len(rows), rows[0][0], rows[-1][0], rows[0][9], rows[-1][9], nf, dup))
    for ln, why, txt in skipped:
        print("   SKIP L%-3d %-20s %s" % (ln, why, txt))


if __name__ == "__main__":
    for n in SPEC:
        run(n)
