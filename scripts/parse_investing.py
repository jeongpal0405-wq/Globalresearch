# -*- coding: utf-8 -*-
"""Investing.com 히스토리 표(수동 복사 원문) -> 이벤트 CSV.

data/raw/<name>.txt 에 붙여넣은 원문을 읽어 data/events/<name>.csv 로 정제한다.
원문은 그대로 보존하고 정제는 사본에서 한다 (CLAUDE.md 4).

애매한 행은 조용히 버리지 않고 SKIP 으로 출력한다.
실행: py -3 scripts/parse_investing.py
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import datetime as dt
import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
EVENTS = os.path.join(ROOT, "data", "events")

# 파일명 -> (indicator, variant, unit)
SPEC = {
    "us_core_cpi": ("US_CORE_CPI", "core_MoM", "%"),
    "us_nfp":      ("US_NFP",      "headline",  "K"),
    "us_ism_mfg":  ("US_ISM_MFG",  "headline",  "index"),
}

MON = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

# "Aug 12, 2026 (Jul)"  /  "Aug 12, 2026"
DATE_RE = re.compile(
    r"^\s*([A-Z][a-z]{2})\s+(\d{1,2}),\s*(\d{4})\s*(?:\(\s*([A-Z][a-z]{2})\s*\))?")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
NUM_RE = re.compile(r"^-?[\d,]+(?:\.\d+)?\s*[%KMB]?$")


def to_num(tok):
    """'0.3%' -> 0.3, '147K' -> 147.0, '-1.2M' -> -1200.0(K), '' -> None"""
    t = tok.strip().replace(",", "")
    if not t or t in {"-", "--", "\u2014"}:
        return None
    mult = 1.0
    if t.endswith("%"):
        t = t[:-1]
    elif t.endswith("K"):
        t = t[:-1]
    elif t.endswith("M"):
        t, mult = t[:-1], 1000.0
    elif t.endswith("B"):
        t, mult = t[:-1], 1000000.0
    try:
        return float(t) * mult
    except ValueError:
        return None


def ref_month(rel_y, rel_m, ref_abbr):
    """참조월. 표기가 있으면 그것을, 없으면 발표월-1로 간주."""
    if ref_abbr and ref_abbr in MON:
        rm = MON[ref_abbr]
        ry = rel_y if rm <= rel_m else rel_y - 1   # 1월 발표의 (Dec) = 전년
        return "%04d-%02d" % (ry, rm)
    m, y = rel_m - 1, rel_y
    if m == 0:
        m, y = 12, y - 1
    return "%04d-%02d" % (y, m)


def parse_line(line):
    m = DATE_RE.match(line)
    if not m:
        return None, "날짜 없음"
    mon, day, year, ref = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    if mon not in MON:
        return None, "월 표기 불명: " + mon
    rel = dt.date(year, MON[mon], day)

    rest = line[m.end():]
    # 탭 우선, 없으면 2칸 이상 공백
    parts = rest.split("\t") if "\t" in rest else re.split(r"\s{2,}", rest)
    parts = [p.strip() for p in parts]
    if parts and parts[0] == "":
        parts.pop(0)          # 날짜 직후 구분자로 생긴 빈 토큰 1개만 제거
    if parts and TIME_RE.match(parts[0]):
        parts = parts[1:]
    # 뒤쪽 빈칸/부가열 정리: 숫자이거나 빈칸인 항목만
    vals = []
    for p in parts:
        if p == "" or NUM_RE.match(p):
            vals.append(p)
        else:
            break
    vals = (vals + ["", "", ""])[:3]
    if all(v == "" for v in vals):
        return None, "수치 없음"

    return {
        "release_date": rel.isoformat(),
        "ref_month": ref_month(year, MON[mon], ref),
        "actual": to_num(vals[0]),
        "forecast": to_num(vals[1]),
        "previous": to_num(vals[2]),
    }, None


def parse_file(path):
    name = os.path.splitext(os.path.basename(path))[0]
    if name not in SPEC:
        print("SKIP FILE %s (SPEC 미등록)" % name)
        return None
    indicator, variant, unit = SPEC[name]
    pulled = dt.date.today().isoformat()

    rows, skipped = [], []
    with open(path, encoding="utf-8-sig") as f:
        for ln, line in enumerate(f, 1):
            if not line.strip():
                continue
            rec, why = parse_line(line.rstrip("\n"))
            if rec is None:
                skipped.append((ln, why, line.strip()[:70]))
                continue
            if rec["actual"] is None:
                skipped.append((ln, "actual 없음(미발표행)", line.strip()[:70]))
                continue
            notes = "" if rec["forecast"] is not None else "forecast 미기재"
            rows.append((rec["release_date"], indicator, variant,
                         rec["actual"], rec["forecast"], rec["previous"],
                         unit, pulled, notes, rec["ref_month"]))

    rows.sort(key=lambda r: r[0])
    out = os.path.join(EVENTS, name + ".csv")
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write("release_date,indicator,variant,actual,forecast,previous,"
                "unit,pulled_on,notes,ref_month\n")
        for r in rows:
            f.write("%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" % (
                r[0], r[1], r[2],
                "" if r[3] is None else r[3],
                "" if r[4] is None else r[4],
                "" if r[5] is None else r[5],
                r[6], r[7], r[8], r[9]))

    nf = sum(1 for r in rows if r[4] is None)
    span = ("%s ~ %s" % (rows[0][0], rows[-1][0])) if rows else "-"
    print("%-14s n=%-4d %s  forecast결측=%d  -> %s" %
          (name, len(rows), span, nf, os.path.relpath(out, ROOT)))
    for ln, why, txt in skipped:
        print("   SKIP L%-4d %-22s %s" % (ln, why, txt))
    return len(rows)


if __name__ == "__main__":
    paths = sorted(glob.glob(os.path.join(RAW, "*.txt")))
    if not paths:
        print("data/raw/ 에 붙여넣은 원문(.txt)이 없음")
        sys.exit(1)
    for p in paths:
        parse_file(p)
