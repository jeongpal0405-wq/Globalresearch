# -*- coding: utf-8 -*-
"""이벤트 테이블 로더 · 검증기.

data/events/*.csv 를 읽어 스키마를 검사하고 surprise 를 파생시킨다.
forecast 공란은 0으로 채우지 않고 NaN 으로 둔다 (CLAUDE.md 4).

실행: py -3 scripts/load_events.py
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import glob
import os
import sys
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, "data", "events")

COLS = ["release_date", "indicator", "variant", "actual", "forecast",
        "previous", "unit", "pulled_on", "notes"]
UNITS = {"%", "K", "index"}


def load_one(path):
    df = pd.read_csv(path, dtype={"notes": str})
    missing = [c for c in COLS if c not in df.columns]
    if missing:
        raise ValueError("%s: 컬럼 누락 %s" % (os.path.basename(path), missing))
    df["release_date"] = pd.to_datetime(df["release_date"])
    for c in ("actual", "forecast", "previous"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["surprise"] = df["actual"] - df["forecast"]
    df["src"] = os.path.basename(path)
    return df.sort_values("release_date").reset_index(drop=True)


def load_all():
    paths = sorted(glob.glob(os.path.join(EVENTS, "*.csv")))
    frames = [load_one(p) for p in paths]
    frames = [f for f in frames if len(f)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLS)


def report(df):
    if df.empty:
        print("이벤트 테이블 비어 있음 — data/events/*.csv 에 Investing.com 히스토리를 붙여넣을 것")
        return False
    ok = True
    for (ind, var), g in df.groupby(["indicator", "variant"]):
        nf = int(g["forecast"].isna().sum())
        bad_unit = sorted(set(g["unit"]) - UNITS)
        dup = int(g["release_date"].duplicated().sum())
        print("%-14s %-14s n=%-4d %s ~ %s  forecast결측=%d  중복일=%d %s" % (
            ind, var, len(g), g.release_date.min().date(), g.release_date.max().date(),
            nf, dup, ("단위오류:%s" % bad_unit) if bad_unit else ""))
        if bad_unit or dup:
            ok = False
    return ok


if __name__ == "__main__":
    sys.exit(0 if report(load_all()) else 1)
