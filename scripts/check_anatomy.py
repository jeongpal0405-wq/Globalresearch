# -*- coding: utf-8 -*-
"""해석 검증 — anatomy 의 모든 문장을 원본 숫자와 대조한다.

기사가 그렇게 말했나를 묻지 않는다. 이 문장을 숫자에서 다시 만들 수 있나를 묻는다.
근거(from)를 못 대는 문장, 근거에 없는 숫자를 쓴 문장은 FAIL 이다.

근거 참조 문법 (from 배열에 넣는 문자열)
  facts.headline.us_core_cpi.surprise
  facts.components.cpi.rows[휘발유].mom
  facts.components.nfp.extra.실업률.cur
  facts.manual.ism.rows[고용].cur
  results.cases[2020-08-12].ret.^IXIC.5
  results.baseline.^IXIC.5.median
  events.us_core_cpi[2020-06].actual

실행: py -3 scripts/check_anatomy.py            (퍼널 통과일 전부)
      py -3 scripts/check_anatomy.py 2020-08-12
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import glob

import json
import os
import re

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "_out")

MAXLEN = 49          # 좌측 열 6.0in · 10pt 에서 한 줄 (CLAUDE.md 6.2)
N_DAY, N_PATH = 3, 4
TOL = 0.0005         # 기여도 합 대조용 오차
CONST = {0.0, 50.0, 100.0}      # 기준선 · 백분율 기준

# 완결형 종결 금지 (개조식 · 음슴체)
BAD_END = re.compile(r"(다|요)\.?$")
# 측정치로 볼 숫자: 부호가 붙었거나, 소수점이 있거나, 단위가 따라붙은 것
NUM = re.compile(r"[+\-−]?\d[\d,]*(?:\.\d+)?")
#   개월 · 개 · 위 · 건 · 번째 도 단위로 본다. 순위 · 표본수 문장을 대조하기 위함
#   ('개월' 은 '개' 보다 먼저 와야 한다)
UNIT = re.compile(r"^\s*(%p|%|K|bp|pt|배|달러|\$|개월|개|위|건|번째)")


def load(date):
    a = json.load(open(os.path.join(DATA, "anatomy", "%s.json" % date), encoding="utf-8"))
    f = json.load(open(os.path.join(DATA, "facts", "%s.json" % date), encoding="utf-8"))
    r = json.load(open(os.path.join(OUT, "results.json"), encoding="utf-8"))
    ev = {}
    for p in glob.glob(os.path.join(DATA, "events", "*.csv")):
        ev[os.path.splitext(os.path.basename(p))[0]] = pd.read_csv(p)
    return a, f, r, ev


# ── 근거 해석 ────────────────────────────────────────────────────────────
def _tok(ref):
    """'a.rows[휘발유].mom' -> ['a', ('rows','휘발유'), 'mom']"""
    out = []
    for part in ref.split("."):
        m = re.match(r"^([^\[]+)\[([^\]]+)\]$", part)
        out.append((m.group(1), m.group(2)) if m else part)
    return out


def _pick(seq, key):
    """리스트에서 name/date/ref_month 가 key 인 원소."""
    for x in seq:
        if isinstance(x, dict) and key in (x.get("name"), x.get("date")):
            return x
    return None


def resolve(ref, facts, res, ev):
    toks = _tok(ref)
    root = toks[0]
    if root == "facts":
        cur = facts
    elif root == "results":
        cur = res
    elif root == "events":
        name = toks[1] if isinstance(toks[1], str) else toks[1][0]
        df = ev.get(name)
        if df is None:
            return None, "알 수 없는 이벤트 파일 '%s'" % name
        if isinstance(toks[1], tuple):
            row = df[df.ref_month == toks[1][1]]
            if row.empty:
                return None, "참조월 %s 없음" % toks[1][1]
            cur = row.iloc[0].to_dict()
        else:
            return None, "events 는 [참조월] 이 필요함"
        toks = toks[1:]
    else:
        return None, "루트는 facts · results · events 만 가능"

    for t in toks[1:]:
        key, sub = (t, None) if isinstance(t, str) else t
        if isinstance(cur, dict):
            if key not in cur:
                return None, "'%s' 없음" % key
            cur = cur[key]
        else:
            return None, "'%s' 를 찾을 수 없음" % key
        if sub is not None:
            if not isinstance(cur, list):
                return None, "'%s' 는 리스트가 아님" % key
            cur = _pick(cur, sub)
            if cur is None:
                return None, "'%s' 안에 '%s' 없음" % (key, sub)
    return cur, None


def measured(text):
    """문장에서 '측정치'만 뽑아 (값, 소수자릿수) 로 준다.

    맨숫자(3분의 1)는 검사 대상이 아니다. 자릿수를 같이 넘기는 이유는,
    고정 허용오차를 쓰면 '0.5' 가 표의 '+0.51' 에 걸려 통과해 버리기 때문이다.
    """
    out = []
    for m in NUM.finditer(text):
        s = m.group(0)
        signed = s[0] in "+-−"
        dec = "." in s
        unit = bool(UNIT.match(text[m.end():]))
        if signed or dec or unit:
            out.append((float(s.replace(",", "").replace("−", "-")),
                        len(s.split(".")[1]) if dec else 0))
    return out


def vals_of(text):
    return [v for v, _ in measured(text)]


def pool_of(refs, block, facts, res, ev, errs, where):
    vals = set(CONST)
    for ref in refs:
        v, err = resolve(ref, facts, res, ev)
        if err:
            errs.append("%s  근거 해석 불가 '%s' — %s" % (where, ref, err))
            continue
        # 근거는 숫자 하나를 가리켜야 한다. 객체를 통째로 짚으면 그 안의 숫자가
        # 전부 인정돼, 자리만 바꾼 '3개월 중 98위' 가 통과한다.
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            errs.append("%s  근거 '%s' 가 숫자 하나를 가리키지 않음 — 잎까지 짚을 것"
                        % (where, ref))
            continue
        vals.add(float(v))
    # 근거는 from 에 적은 것만 인정한다. 다음 둘은 일부러 빼놨다.
    #  - 같은 블록 표의 숫자 자동 포함: CPI 표는 전부 작은 소수라 '+0.51' 을
    #    정수 자리로 반올림하면 1 이 되어 '1위' 같은 날조가 통과했다.
    #  - 두 값의 차이: 표 숫자 20개면 조합이 400개가 되어 작은 정수를 다 덮는다.
    # 표 값을 인용하려면 그 항목을 from 에 적는다. 차이를 쓰려면 그 값을 담은
    # 필드를 근거로 대거나 문장을 바꾼다.
    return vals


def hit(x, d, pool):
    """글에 쓴 자릿수로 반올림해서 같으면 인정."""
    return any(round(p, d) == round(x, d) for p in pool)


# ── 검사 ─────────────────────────────────────────────────────────────────
def check_line(item, block, facts, res, ev, errs, where):
    if not isinstance(item, dict) or "text" not in item or "from" not in item:
        errs.append("%s  {text, from} 형태가 아님 — 옛 포맷이면 해석 에이전트로 다시 생성" % where)
        return
    t = item["text"]
    if len(t) > MAXLEN:
        errs.append("%s  %d자 (상한 %d) — %s" % (where, len(t), MAXLEN, t[:30]))
    if BAD_END.search(t.strip()):
        errs.append("%s  완결형 종결 — %s" % (where, t[-14:]))
    if not item["from"]:
        errs.append("%s  근거 없음 — %s" % (where, t[:30]))
        return
    pool = pool_of(item["from"], block, facts, res, ev, errs, where)
    for x, d in measured(t):
        if not hit(x, d, pool):
            errs.append("%s  근거에 없는 숫자 %g — %s" % (where, x, t[:30]))


def check(date):
    a, f, res, ev = load(date)
    errs = []

    n_cond = len(f["headline"])
    if len(a.get("anatomy", [])) != n_cond:
        errs.append("해부 블록 %d개, 조건 %d개 — 개수가 달라야 할 이유 없음"
                    % (len(a.get("anatomy", [])), n_cond))

    for blk in a.get("anatomy", []):
        w = "[%s]" % blk.get("cond", "?")
        for k in ("cond", "name", "headline", "cols", "align", "rows", "note", "src"):
            if not blk.get(k):
                errs.append("%s  '%s' 비어 있음" % (w, k))
        if blk.get("cols") and blk.get("align") and len(blk["cols"]) != len(blk["align"]):
            errs.append("%s  cols %d개 · align %d개" % (w, len(blk["cols"]), len(blk["align"])))
        for i, row in enumerate(blk.get("rows", [])):
            if blk.get("cols") and len(row) != len(blk["cols"]):
                errs.append("%s  %d행 칸 수 %d ≠ 열 %d" % (w, i, len(row), len(blk["cols"])))
        note = blk.get("note", [])
        if len(note) > 2:
            errs.append("%s  note %d줄 (상한 2)" % (w, len(note)))
        for i, nt in enumerate(note):
            check_line(nt, blk, f, res, ev, errs, "%s note%d" % (w, i + 1))
        if not str(blk.get("src", "")).startswith("자료:"):
            errs.append("%s  src 가 '자료:' 로 시작하지 않음" % w)

    for key, want in (("day", N_DAY), ("path", N_PATH)):
        seq = a.get(key, [])
        if len(seq) != want:
            errs.append("[%s]  %d줄 (규격 %d)" % (key, len(seq), want))
        for i, it in enumerate(seq):
            check_line(it, None, f, res, ev, errs, "[%s]%d" % (key, i + 1))

    rd = a.get("read")
    if not rd:
        errs.append("[read]  없음 — 슬라이드당 해석 1줄은 필수")
    else:
        check_line(rd, None, f, res, ev, errs, "[read]")

    # CPI 기여도 합 = 합계 ± 잔차 (반올림으로 맞추지 않는다)
    for blk in a.get("anatomy", []):
        if "기여도(%p)" not in blk.get("cols", []):
            continue
        j = blk["cols"].index("기여도(%p)")
        vals, total = [], None
        last = blk["rows"][-1] if blk.get("total_row") else None
        for row in blk["rows"]:
            v = vals_of(str(row[j]))
            if not v:
                continue
            if row is last:
                total = v[0]
            else:
                vals.append(v[0])
        if total is not None and abs(sum(vals) - total) > TOL:
            errs.append("[%s]  기여도 합 %+.3f ≠ 합계 %+.3f — 잔차 행으로 남길 것"
                        % (blk.get("cond", "?"), sum(vals), total))

    print("%s  %s  (오류 %d건)" % (date, "PASS" if not errs else "FAIL", len(errs)))
    for e in errs:
        print("   ", e)
    if f.get("missing"):
        print("    확보 실패 %d건 (FAIL 아님, 보고서에 '확보 실패'로 표기됨)" % len(f["missing"]))
    return not errs


def main(argv):
    dates = argv[1:] or [os.path.splitext(os.path.basename(p))[0]
                         for p in sorted(glob.glob(os.path.join(DATA, "facts", "*.json")))]
    ok = all([check(d) for d in dates])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
