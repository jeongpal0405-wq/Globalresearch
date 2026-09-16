# -*- coding: utf-8 -*-
"""yfinance 가격 로컬 캐시 (Parquet, 증분 갱신).

수정종가(adj_close)와 원본종가(close)를 함께 저장한다.
"""
import os
import time
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data", "prices")
os.makedirs(CACHE, exist_ok=True)

START = "1999-12-01"


def _path(ticker):
    return os.path.join(CACHE, ticker.replace("^", "_") + ".parquet")


def _download(ticker, start):
    df = yf.download(ticker, start=start, auto_adjust=False,
                     progress=False, threads=False)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    out = pd.DataFrame({
        "close": df["Close"].astype(float),
        "adj_close": df["Adj Close"].astype(float),
    })
    out.index = pd.to_datetime(out.index).tz_localize(None).normalize()
    out.index.name = "date"
    return out[~out.index.duplicated(keep="last")].dropna()


def get(ticker, start=START, refresh=True):
    """캐시를 읽고, 필요하면 마지막 날짜 이후만 추가로 받아 갱신한다."""
    p = _path(ticker)
    cached = pd.read_parquet(p) if os.path.exists(p) else None

    if cached is None:
        fresh = _download(ticker, start)
        if fresh is None:
            raise RuntimeError("no data: " + ticker)
        fresh.to_parquet(p)
        return fresh

    if refresh:
        last = cached.index.max()
        if last < pd.Timestamp.today().normalize():
            add = _download(ticker, (last + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
            if add is not None and not add.empty:
                cached = pd.concat([cached, add])
                cached = cached[~cached.index.duplicated(keep="last")].sort_index()
                cached.to_parquet(p)
    return cached


def get_many(tickers, start=START, delay=1.0):
    out = {}
    for t in tickers:
        out[t] = get(t, start)
        time.sleep(delay)
    return out


if __name__ == "__main__":
    import sys
    for t in sys.argv[1:]:
        d = get(t)
        print("%-8s %s ~ %s  n=%d" % (t, d.index.min().date(), d.index.max().date(), len(d)))
        time.sleep(1.0)
