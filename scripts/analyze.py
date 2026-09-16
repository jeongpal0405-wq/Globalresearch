# -*- coding: utf-8 -*-
"""삼중 조건 이벤트 스터디 — 성과 계산.

실행: py -3 scripts/analyze.py
산출: _out/results.json (보고서 생성이 읽음)
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eventstudy as es
import screen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_out")
os.makedirs(OUT, exist_ok=True)

H = [1, 5, 20, 60]
HD = [0] + H          # 0 = 발표일 당일
BASE_START, BASE_END = "2018-06-01", "2026-08-27"
NAMES = {"^GSPC": "S&P500", "^IXIC": "나스닥", "^SOX": "SOX", "^RUT": "러셀2000"}


def basket(px, tickers, date, h):
    """동일가중 바스켓 포워드 수익률 = 구성 ETF 수익률의 단순평균.

    h=0 은 발표일 당일(전일 종가 -> 당일 종가).
    """
    g = es.release_day if h == 0 else (lambda s, d: es.forward(s, d, h))
    v = [g(px[t], date) for t in tickers]
    v = [x for x in v if not np.isnan(x)]
    return float(np.mean(v)) if v else np.nan


def basket_baseline(px, tickers, h):
    """바스켓의 무조건부 베이스라인 — 구성 ETF 수익률을 날짜별로 평균 후 통계."""
    mat = []
    for t in tickers:
        s = px[t]
        s = s[(s.index >= pd.Timestamp(BASE_START)) & (s.index <= pd.Timestamp(BASE_END))]
        a = s.to_numpy()
        mat.append((a[h:] / a[:-h] - 1.0) * 100.0)
    n = min(len(x) for x in mat)
    return es.summarize(np.mean([x[:n] for x in mat], axis=0))


def rank_of(series, v):
    """표본 안에서 이 값 이상인 달이 몇 개인가. rank=1 이면 최고치.

    보고서에 '98개월 중 2번째' 류 문장을 쓰려면 이 값이 results.json 에 있어야 한다.
    없으면 check_anatomy 가 대조할 근거가 없다.
    """
    s = series.dropna()
    ge = int((s >= v).sum())
    return {"rank": ge, "n": int(len(s)), "pct": _r(100.0 * ge / len(s))}


def main():
    m = screen.build()
    m = m[~((m.nfp_date > m.cpi_date) | (m.ism_date > m.cpi_date))]
    a = m[m.cpi_surp >= screen.CPI_PP]
    b = a[a.nfp_surp >= screen.NFP_K]
    c = b[b.ism_act >= screen.ISM_LV]

    tickers = es.TARGETS + es.CYCLICAL + es.DEFENSIVE
    px = es.load(tickers)
    dates = list(c["event_date"])

    res = {
        "funnel": {"all": int(len(m)), "A": int(len(a)), "B": int(len(b)), "C": int(len(c))},
        "thresholds": {"cpi_pp": screen.CPI_PP, "nfp_k": screen.NFP_K, "ism": screen.ISM_LV},
        "data_span": {"cpi": [str(m.cpi_date.min().date()), str(m.cpi_date.max().date())],
                      "base": [BASE_START, BASE_END]},
        "horizons": HD,
        "stageA": [], "cases": [], "baseline": {}, "basket_baseline": {},
    }

    # A단계 6건 — 어디서 탈락했는지
    for _, r in a.iterrows():
        res["stageA"].append({
            "date": str(r.event_date.date()), "ref": r.ref_month,
            "cpi_surp": round(float(r.cpi_surp), 2),
            "nfp_surp": None if pd.isna(r.nfp_surp) else float(r.nfp_surp),
            "ism": None if pd.isna(r.ism_act) else float(r.ism_act),
            "pass_B": bool(r.nfp_surp >= screen.NFP_K) if not pd.isna(r.nfp_surp) else False,
            "pass_C": bool(r.ism_act >= screen.ISM_LV) if not pd.isna(r.ism_act) else False,
        })

    # 최종 사례별 성과
    for _, r in c.iterrows():
        d = r.event_date
        item = {"date": str(d.date()), "ref": r.ref_month,
                "cpi_act": float(r.cpi_act), "cpi_fc": float(r.cpi_fc),
                "cpi_surp": round(float(r.cpi_surp), 2),
                "nfp_act": float(r.nfp_act), "nfp_fc": float(r.nfp_fc),
                "nfp_surp": float(r.nfp_surp), "ism": float(r.ism_act),
                "rank": {"cpi_surp": rank_of(m.cpi_surp, r.cpi_surp),
                         "nfp_surp": rank_of(m.nfp_surp, r.nfp_surp),
                         "ism": rank_of(m.ism_act, r.ism_act)},
                "ret": {}, "mdd60": {}}
        for t in tickers:
            item["ret"][t] = {str(h): _r(es.forward(px[t], d, h)) for h in H}
            item["ret"][t]["0"] = _r(es.release_day(px[t], d))
            item["mdd60"][t] = _r(es.max_drawdown(px[t], d, 60))
        for nm, tk in (("CYC", es.CYCLICAL), ("DEF", es.DEFENSIVE)):
            item["ret"][nm] = {str(h): _r(basket(px, tk, d, h)) for h in HD}
        item["ret"]["CYC_DEF"] = {str(h): _r(item["ret"]["CYC"][str(h)] - item["ret"]["DEF"][str(h)])
                                  for h in HD}
        res["cases"].append(item)

    # 무조건부 베이스라인
    bl = es.baseline(px, BASE_START, BASE_END, H)
    for _, r in bl.iterrows():
        res["baseline"].setdefault(r.ticker, {})[str(int(r.h))] = {
            "n": int(r.n), "mean": _r(r["mean"]), "median": _r(r["median"]), "win": _r(r["win"])}
    for nm, tk in (("CYC", es.CYCLICAL), ("DEF", es.DEFENSIVE)):
        res["basket_baseline"][nm] = {}
        for h in H:
            s = basket_baseline(px, tk, h)
            res["basket_baseline"][nm][str(h)] = {
                "n": s["n"], "mean": _r(s["mean"]), "median": _r(s["median"]), "win": _r(s["win"])}

    # 사례 간 간격 -> 윈도우 중첩
    if len(dates) > 1:
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        res["gaps_days"] = gaps
        res["overlap60"] = int(sum(1 for g in gaps if g < 60 * 7 / 5))
    else:
        res["gaps_days"], res["overlap60"] = [], 0

    with open(os.path.join(OUT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    # 콘솔 요약
    print("퍼널  전체 %d -> A %d -> B %d -> C %d" %
          (res["funnel"]["all"], res["funnel"]["A"], res["funnel"]["B"], res["funnel"]["C"]))
    print("\nA단계 %d건 (Core CPI 서프 >= +%.2f%%p)" % (len(res["stageA"]), screen.CPI_PP))
    print(" date        ref      surp   NFP서프    ISM   B  C")
    for s in res["stageA"]:
        print(" %s  %s  %+5.2f  %8s  %5s  %s  %s" % (
            s["date"], s["ref"], s["cpi_surp"],
            "-" if s["nfp_surp"] is None else "%+.0fK" % s["nfp_surp"],
            "-" if s["ism"] is None else "%.1f" % s["ism"],
            "O" if s["pass_B"] else "X", "O" if s["pass_C"] else "X"))
    print("\n최종 2건 포워드 수익률 (%)")
    hdr = "  ".join("%7s" % ("%dd" % h) for h in H)
    for cse in res["cases"]:
        print("\n[%s] 참조월 %s  CPI %.1f vs %.1f (%+.2f%%p)  NFP %+.0fK  ISM %.1f" % (
            cse["date"], cse["ref"], cse["cpi_act"], cse["cpi_fc"], cse["cpi_surp"],
            cse["nfp_surp"], cse["ism"]))
        print("  %-10s %s   %s" % ("", hdr, "MDD60"))
        for t in es.TARGETS:
            print("  %-10s %s   %6.2f" % (
                NAMES[t], "  ".join("%+7.2f" % cse["ret"][t][str(h)] for h in H),
                cse["mdd60"][t]))
        for k, lab in (("CYC", "경기민감"), ("DEF", "방어"), ("CYC_DEF", "민감-방어")):
            print("  %-10s %s" % (lab, "  ".join("%+7.2f" % cse["ret"][k][str(h)] for h in H)))
    print("\n무조건부 베이스라인 중앙값 (%s ~ %s)" % (BASE_START, BASE_END))
    print("  %-10s %s" % ("", hdr))
    for t in es.TARGETS:
        print("  %-10s %s" % (NAMES[t], "  ".join(
            "%+7.2f" % res["baseline"][t][str(h)]["median"] for h in H)))
    for k, lab in (("CYC", "경기민감"), ("DEF", "방어")):
        print("  %-10s %s" % (lab, "  ".join(
            "%+7.2f" % res["basket_baseline"][k][str(h)]["median"] for h in H)))


def _r(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 2)


if __name__ == "__main__":
    main()
