# -*- coding: utf-8 -*-
"""삼중 조건 퍼널 스크리너.

참조월(ref_month)로 Core CPI / NFP / ISM 을 정렬하고,
이벤트일은 셋 중 가장 늦게 발표되는 Core CPI 발표일로 잡는다.

조건 (원 요청 그대로, 완화 없음):
  A. Core CPI MoM surprise >= +0.20 %p
  B. NFP surprise         >= +100 K
  C. ISM 제조업 actual    >= 50.0

실행: py -3 scripts/screen.py
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, "data", "events")

START = "2010-01-01"
CPI_PP = 0.20
NFP_K = 100.0
ISM_LV = 50.0


def read(name):
    p = os.path.join(EVENTS, name + ".csv")
    df = pd.read_csv(p)
    if df.empty:
        raise SystemExit("비어 있음: %s — data/raw/%s.txt 붙여넣고 parse_investing.py 실행" % (p, name))
    df["release_date"] = pd.to_datetime(df["release_date"])
    # 반올림 필수. 0.6 - 0.2 = 0.19999999999999996 이라 임계값 비교에서 탈락한다.
    # 원본이 소수 1자리(%)·정수(K)이므로 2자리면 충분하다.
    df["surprise"] = (df["actual"] - df["forecast"]).round(2)
    return df


def build():
    cpi = read("us_core_cpi").rename(columns={
        "release_date": "cpi_date", "actual": "cpi_act",
        "forecast": "cpi_fc", "surprise": "cpi_surp"})
    nfp = read("us_nfp").rename(columns={
        "release_date": "nfp_date", "actual": "nfp_act",
        "forecast": "nfp_fc", "surprise": "nfp_surp"})
    ism = read("us_ism_mfg").rename(columns={
        "release_date": "ism_date", "actual": "ism_act"})

    m = cpi[["ref_month", "cpi_date", "cpi_act", "cpi_fc", "cpi_surp"]] \
        .merge(nfp[["ref_month", "nfp_date", "nfp_act", "nfp_fc", "nfp_surp"]],
               on="ref_month", how="left") \
        .merge(ism[["ref_month", "ism_date", "ism_act"]], on="ref_month", how="left")
    m = m[m["cpi_date"] >= pd.Timestamp(START)].sort_values("cpi_date").reset_index(drop=True)
    m["event_date"] = m["cpi_date"]
    return m


def check_lookahead(m):
    """이벤트일(=CPI 발표일) 시점에 NFP·ISM 이 이미 공개돼 있어야 한다."""
    bad = m[(m.nfp_date > m.cpi_date) | (m.ism_date > m.cpi_date)]
    return bad[["ref_month", "cpi_date", "nfp_date", "ism_date"]]


def funnel(m):
    # 이벤트일 시점에 미공개인 지표가 섞인 행은 조건 판정에서 제외 (룩어헤드 금지)
    m = m[~((m.nfp_date > m.cpi_date) | (m.ism_date > m.cpi_date))]
    a = m[m.cpi_surp >= CPI_PP]
    b = a[a.nfp_surp >= NFP_K]
    c = b[b.ism_act >= ISM_LV]
    return m, a, b, c


if __name__ == "__main__":
    m = build()
    bad = check_lookahead(m)
    if len(bad):
        print("경고: 이벤트일보다 늦게 발표된 지표가 섞임 (%d행) — 룩어헤드" % len(bad))
        print(bad.to_string(index=False))

    miss = m[m.nfp_surp.isna() | m.ism_act.isna()]
    if len(miss):
        print("참조월 매칭 실패/결측 %d행 (해당 월은 조건 판정 불가로 제외됨)" % len(miss))

    full, a, b, c = funnel(m)
    print("\n퍼널 (%s ~, 참조월 정렬 · 이벤트일=Core CPI 발표일)" % START)
    print("  전체 CPI 발표월           : %d" % len(full))
    print("  A. Core CPI 서프 >= +%.2f%%p : %d" % (CPI_PP, len(a)))
    print("  B.  + NFP 서프 >= +%dK     : %d" % (int(NFP_K), len(b)))
    print("  C.  + ISM >= %.1f          : %d" % (ISM_LV, len(c)))

    if len(c):
        print("\n최종 사례")
        print(c[["event_date", "ref_month", "cpi_act", "cpi_fc", "cpi_surp",
                 "nfp_act", "nfp_fc", "nfp_surp", "ism_act"]].to_string(index=False))
    else:
        print("\n조건 충족 사례 없음")
