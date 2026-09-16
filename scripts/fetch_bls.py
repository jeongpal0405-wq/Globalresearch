# -*- coding: utf-8 -*-
"""finalist 날짜의 지표 세부값 수집 — BLS 공개 API.

퍼널을 통과한 날짜에 대해서만 돈다 (CLAUDE.md 규칙 B).
후보군 생성에는 절대 쓰지 않는다 — 조건 판정은 data/events/*.csv 가 전부 한다.

주의. API 는 오늘 기준으로 재계산된 계절조정 지수를 준다. 발표 당시 값이 아니다.
     헤드라인(actual/forecast/surprise)은 발표 당시 값인 data/events 에서만 가져온다.

실행: py -3 scripts/fetch_bls.py              (퍼널 통과일 전부)
      py -3 scripts/fetch_bls.py 2020-08-12   (날짜 지정)
산출: data/facts/<기산일>.json
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import datetime as dt
import json
import os
import urllib.request

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import screen

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FACTS = os.path.join(DATA, "facts")
API = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
CHUNK = 25          # v1 은 1회 25개 시리즈까지


def fetch(ids, y0, y1):
    """시리즈 ID -> {"YYYY-MM": 값} 딕셔너리."""
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), CHUNK):
        body = json.dumps({"seriesid": ids[i:i + CHUNK],
                           "startyear": str(y0), "endyear": str(y1)}).encode()
        req = urllib.request.Request(API, data=body,
                                     headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=60))
        if r.get("status") != "REQUEST_SUCCEEDED":
            raise SystemExit("BLS API 실패: %s" % r.get("message"))
        for s in r["Results"]["series"]:
            out[s["seriesID"]] = {
                "%s-%02d" % (d["year"], int(d["period"][1:])): float(d["value"])
                for d in s["data"] if d["period"].startswith("M")}
    return out


def prev_month(ym, k=1):
    y, m = int(ym[:4]), int(ym[5:7])
    for _ in range(k):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return "%04d-%02d" % (y, m)


def mom(series, ym):
    """전월비 %. 값이 없으면 None."""
    p = prev_month(ym)
    if ym not in series or p not in series or series[p] == 0:
        return None
    return round((series[ym] / series[p] - 1.0) * 100.0, 2)


def cpi_block(smap, weights, raw, ym, missing):
    comp, rows = smap["cpi"]["components"], []
    wy = weights[weights.year == int(ym[:4])].set_index("component")["weight"].to_dict()
    if not wy:
        missing.append("cpi.weights[%s] — data/weights/cpi_relimp.csv 에 %s년 비중 없음"
                       % (ym[:4], ym[:4]))
    for name, sid in comp.items():
        m = mom(raw.get(sid, {}), ym)
        w = wy.get(name)
        if m is None or w is None:
            continue
        rows.append({"name": name, "mom": m, "weight": round(w, 2),
                     "contrib": round(m * w / 100.0, 3)})
    rows.sort(key=lambda r: -abs(r["contrib"]))
    total = mom(raw.get(smap["cpi"]["total"], {}), ym)
    core = mom(raw.get(smap["cpi"]["core"], {}), ym)
    ssum = round(sum(r["contrib"] for r in rows), 3)
    return {
        "unit": "%",
        "vintage": "revised",
        "total_mom": total,
        "core_mom": core,
        "rows": rows,
        "sum_contrib": ssum,
        "residual": None if total is None else round(total - ssum, 3),
        "src": "자료: BLS API, CPI-U 계절조정 지수(CUSR). 비중은 "
               "data/weights/cpi_relimp.csv, 기여도 = 전월비 x 비중, 자체 계산",
    }


def nfp_block(smap, raw, ym, missing):
    ind, rows = smap["nfp"]["industries"], []
    p1, p2 = prev_month(ym), prev_month(ym, 2)
    for name, sid in ind.items():
        s = raw.get(sid, {})
        if ym not in s or p1 not in s or p2 not in s:
            continue
        rows.append({"name": name,
                     "cur": round(s[ym] - s[p1], 1),
                     "prev": round(s[p1] - s[p2], 1)})
    rows.sort(key=lambda r: -r["cur"])
    t = raw.get(smap["nfp"]["total"], {})
    tot_cur = round(t[ym] - t[p1], 1) if ym in t and p1 in t else None
    tot_prev = round(t[p1] - t[p2], 1) if p1 in t and p2 in t else None
    listed = round(sum(r["cur"] for r in rows), 1)
    extra = {}
    for name, sid in smap["nfp"]["extra"].items():
        s = raw.get(sid, {})
        if ym in s:
            extra[name] = {"cur": s[ym], "prev": s.get(p1)}
    return {
        "unit": "K",
        "vintage": "revised",
        "cols": ["업종", ym, p1],
        "total": {"cur": tot_cur, "prev": tot_prev},
        "rows": rows,
        "sum_listed": listed,
        "residual": None if tot_cur is None else round(tot_cur - listed, 1),
        "extra": extra,
        "src": "자료: BLS API, CES 전체 취업자 계절조정. 단위 천 명(K), 전월 대비 증감",
    }


def build(date, m, smap, weights):
    row = m[m.event_date == pd.Timestamp(date)]
    if row.empty:
        raise SystemExit("퍼널에 없는 날짜: %s" % date)
    r = row.iloc[0]
    ym = r.ref_month
    y = int(ym[:4])

    ids = [smap["cpi"]["total"], smap["cpi"]["core"]] \
        + list(smap["cpi"]["components"].values()) \
        + [smap["nfp"]["total"]] + list(smap["nfp"]["industries"].values()) \
        + list(smap["nfp"]["extra"].values())
    raw = fetch(ids, y - 1, y)

    missing = []
    facts = {
        "date": date,
        "ref_month": ym,
        "pulled_on": dt.date.today().isoformat(),
        "headline": {
            "us_core_cpi": {"actual": float(r.cpi_act), "forecast": float(r.cpi_fc),
                            "surprise": round(float(r.cpi_surp), 2), "unit": "%",
                            "release_date": str(r.cpi_date.date()),
                            "vintage": "as_released"},
            "us_nfp": {"actual": float(r.nfp_act), "forecast": float(r.nfp_fc),
                       "surprise": round(float(r.nfp_surp), 1), "unit": "K",
                       "release_date": str(r.nfp_date.date()),
                       "vintage": "as_released"},
            "us_ism_mfg": {"actual": float(r.ism_act), "unit": "index",
                           "release_date": str(r.ism_date.date()),
                           "vintage": "as_released"},
        },
        "components": {
            "cpi": cpi_block(smap, weights, raw, ym, missing),
            "nfp": nfp_block(smap, raw, ym, missing),
        },
        "manual": {},
        "missing": missing,
    }

    mp = os.path.join(DATA, "manual", "%s.json" % date)
    if os.path.exists(mp):
        facts["manual"] = json.load(open(mp, encoding="utf-8"))
        missing.extend(facts["manual"].get("miss", []))
    else:
        missing.append("manual[%s] — ISM 세부지수 등 수동 입력 파일 없음" % date)

    # 개정폭은 발표 당시 vintage 라야 나온다. API 는 현재 개정판만 주므로 수동에서만 온다.
    if not facts["manual"].get("nfp_as_released", {}).get("revisions_k"):
        missing.append("nfp.revisions — 개정폭 없음. data/manual 의 "
                       "nfp_as_released.revisions_k 에 넣어야 함")
    if not facts["manual"].get("ism", {}).get("rows"):
        missing.append("ism.sub_indices — ISM 세부지수 없음. 해당 해부 표는 '확보 실패'")
    return facts


def main(argv):
    smap = json.load(open(os.path.join(DATA, "series_map.json"), encoding="utf-8"))
    weights = pd.read_csv(os.path.join(DATA, "weights", "cpi_relimp.csv"), comment="#")
    m = screen.build()
    _, _, _, c = screen.funnel(m)
    dates = argv[1:] or [str(d.date()) for d in c["event_date"]]

    os.makedirs(FACTS, exist_ok=True)
    for d in dates:
        f = build(d, m, smap, weights)
        p = os.path.join(FACTS, "%s.json" % d)
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(f, fh, ensure_ascii=False, indent=1)
        cpi, nfp = f["components"]["cpi"], f["components"]["nfp"]
        print("%s (참조월 %s)" % (d, f["ref_month"]))
        print("   CPI  항목 %d개 · 합계 %+.2f%% · 열거분 %+.3f%%p · 잔차 %+.3f%%p"
              % (len(cpi["rows"]), cpi["total_mom"], cpi["sum_contrib"], cpi["residual"]))
        print("   NFP  업종 %d개 · 총 %+.0fK · 열거분 %+.0fK · 잔차 %+.0fK"
              % (len(nfp["rows"]), nfp["total"]["cur"], nfp["sum_listed"], nfp["residual"]))
        print("   확보 실패 %d건" % len(f["missing"]))
        for x in f["missing"]:
            print("      - %s" % x)
        print("   ->", p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
