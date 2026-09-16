# -*- coding: utf-8 -*-
"""이벤트 스터디 계산 엔진 — 포워드 수익률 · 요약통계 · 무조건부 베이스라인."""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import numpy as np
import pandas as pd

import prices

HORIZONS = [1, 5, 20, 60]

TARGETS = ["^GSPC", "^IXIC", "^SOX", "^RUT"]
CYCLICAL = ["XLI", "XLY", "XLF", "XLB"]
DEFENSIVE = ["XLP", "XLU", "XLV"]


def load(tickers, start=None):
    out = {}
    for t in tickers:
        s = prices.get(t, refresh=False)["adj_close"]
        out[t] = s[s.index >= pd.Timestamp(start)] if start else s
    return out


def anchor(idx, date):
    """이벤트일을 거래일에 맞춘다. 휴장이면 다음 거래일. (당일 종가 기준 진입)"""
    pos = idx.searchsorted(pd.Timestamp(date), side="left")
    return pos if pos < len(idx) else None


def forward(series, date, h):
    """t 종가 → t+h 종가 수익률(%). 데이터가 모자라면 NaN."""
    i = anchor(series.index, date)
    if i is None or i + h >= len(series):
        return np.nan
    return (series.iloc[i + h] / series.iloc[i] - 1.0) * 100.0


def release_day(series, date):
    """발표일 당일 수익률(%) — 전일 종가 -> 당일 종가.

    CPI · NFP 는 08:30 ET(장 시작 전) 발표라 당일 종가가 첫 반응이다.
    ISM(10:00 ET)처럼 장중 발표가 기준일 때는 발표 전 시간대가 섞인다.
    """
    i = anchor(series.index, date)
    if i is None or i == 0:
        return np.nan
    return (series.iloc[i] / series.iloc[i - 1] - 1.0) * 100.0


def max_drawdown(series, date, h):
    """t~t+h 구간 종가 기준 최대낙폭(%). 음수."""
    i = anchor(series.index, date)
    if i is None or i + h >= len(series):
        return np.nan
    w = series.iloc[i:i + h + 1]
    return float((w / w.cummax() - 1.0).min() * 100.0)


def summarize(vals):
    v = pd.Series(vals, dtype=float).dropna()
    if len(v) == 0:
        return dict(n=0, mean=np.nan, median=np.nan, win=np.nan, std=np.nan)
    return dict(n=int(len(v)), mean=float(v.mean()), median=float(v.median()),
                win=float((v > 0).mean() * 100.0), std=float(v.std(ddof=1)))


def event_table(px, dates, horizons=HORIZONS):
    """{ticker: {h: [수익률...]}} 및 사례별 원본을 함께 반환."""
    rows = []
    for d in dates:
        for t, s in px.items():
            r = {"date": pd.Timestamp(d), "ticker": t}
            for h in horizons:
                r["r%d" % h] = forward(s, d, h)
            r["mdd60"] = max_drawdown(s, d, max(horizons))
            rows.append(r)
    return pd.DataFrame(rows)


def baseline(px, start, end, horizons=HORIZONS):
    """무조건부 베이스라인 — 구간 내 모든 거래일을 시작점으로."""
    rows = []
    for t, s in px.items():
        s = s[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]
        a = s.to_numpy()
        for h in horizons:
            if len(a) <= h:
                continue
            r = (a[h:] / a[:-h] - 1.0) * 100.0
            st = summarize(r)
            st.update(ticker=t, h=h)
            rows.append(st)
    return pd.DataFrame(rows)[["ticker", "h", "n", "mean", "median", "win", "std"]]


if __name__ == "__main__":
    import sys
    start, end = sys.argv[1], sys.argv[2]
    px = load(TARGETS + CYCLICAL + DEFENSIVE)
    b = baseline(px, start, end)
    print("무조건부 베이스라인  %s ~ %s" % (start, end))
    print("ticker   h      n    mean   median   win%")
    for _, r in b.iterrows():
        print("%-7s %3d %6d  %+6.2f  %+6.2f  %5.1f" %
              (r.ticker, r.h, r.n, r["mean"], r["median"], r["win"]))
