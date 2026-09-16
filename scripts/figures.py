# -*- coding: utf-8 -*-
"""사례별 그림 생성 -> _out/case{N}_path.png, case{N}_bar.png

CLAUDE.md 6.2 차트 규격: 가로 5.8in 이상 · dpi 200 이상 · 상/우 spine 제거 ·
격자는 가로선만 · 계열색은 pptx_kit.SERIES_COLOR (명도 단계).
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eventstudy as es
from pptx_kit import SERIES_COLOR

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_out")

NAMES = {"^GSPC": "S&P500", "^IXIC": "나스닥", "^SOX": "SOX", "^RUT": "러셀2000",
         "CYC": "경기민감", "DEF": "방어"}
SERIES = ["^GSPC", "^IXIC", "^SOX", "^RUT", "CYC", "DEF"]
HD = [0, 1, 5, 20, 60]
HLAB = ["당일", "1일", "5일", "20일", "60일"]
PRE, POST = 20, 60
DPI = 200
FW = 6.10                     # 슬라이드 우측 열 폭에 맞춘 가로 (>= 5.8in)


def _frame(ax):
    """상/우 spine 제거, 격자는 가로선만."""
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#BBBBBB")
        ax.spines[s].set_linewidth(0.8)
    ax.yaxis.grid(True, color="#DDDDDD", lw=0.6, alpha=0.9)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8, colors="#444444", length=3)


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return p


def basket_path(px, tickers, d):
    """동일가중 바스켓의 정규화 경로 = 구성 ETF 정규화 경로의 평균."""
    arrs = []
    for t in tickers:
        s = px[t]
        i = es.anchor(s.index, d)
        w = s.iloc[max(0, i - PRE):i + POST + 1].to_numpy()
        arrs.append(w / s.iloc[i])
    n = min(len(a) for a in arrs)
    return np.mean([a[:n] for a in arrs], axis=0)


def path_fig(res, idx, px):
    cse = res["cases"][idx]
    d = pd.Timestamp(cse["date"])
    fig, ax = plt.subplots(figsize=(FW, 1.95), dpi=DPI)
    for k in SERIES:
        if k in ("CYC", "DEF"):
            arr = basket_path(px, es.CYCLICAL if k == "CYC" else es.DEFENSIVE, d)
        else:
            s = px[k]
            i = es.anchor(s.index, d)
            arr = s.iloc[max(0, i - PRE):i + POST + 1].to_numpy() / s.iloc[i]
        ax.plot(np.arange(len(arr)) - PRE, (arr - 1) * 100, lw=1.5,
                color=SERIES_COLOR[k], label=NAMES[k],
                alpha=1.0 if k not in ("CYC", "DEF") else 0.8)
    ax.axvline(0, color="#1A1A1A", lw=1.0, ls=(0, (4, 3)))
    ax.axhline(0, color="#888888", lw=0.8)
    ax.annotate("발표일", (0, 1), xycoords=("data", "axes fraction"),
                xytext=(4, -12), textcoords="offset points",
                fontsize=8, color="#1A1A1A")
    ax.set_xlabel("이벤트 기준 거래일", fontsize=8.5, color="#444444")
    ax.set_ylabel("누적 수익률 (%)", fontsize=8.5, color="#444444")
    _frame(ax)
    ax.legend(fontsize=8, ncol=6, frameon=False, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), columnspacing=1.4, handlelength=1.6)
    return save(fig, "case%d_path.png" % (idx + 1))


def bar_fig(res, idx):
    cse = res["cases"][idx]
    fig, ax = plt.subplots(figsize=(FW, 2.05), dpi=DPI)
    x = np.arange(len(HD))
    w = 0.14
    for j, k in enumerate(SERIES):
        v = [cse["ret"][k][str(h)] for h in HD]
        ax.bar(x + (j - 2.5) * w, v, w, color=SERIES_COLOR[k], label=NAMES[k])
    ax.axhline(0, color="#888888", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(HLAB, fontsize=9)
    ax.set_ylabel("수익률 (%)", fontsize=8.5, color="#444444")
    _frame(ax)
    ax.legend(fontsize=8, ncol=6, frameon=False, loc="lower center",
              bbox_to_anchor=(0.5, 1.0), columnspacing=1.4, handlelength=1.6)
    return save(fig, "case%d_bar.png" % (idx + 1))


if __name__ == "__main__":
    res = json.load(open(os.path.join(OUT, "results.json"), encoding="utf-8"))
    px = es.load(es.TARGETS + es.CYCLICAL + es.DEFENSIVE)
    for i in range(len(res["cases"])):
        print("saved:", os.path.basename(path_fig(res, i, px)),
              os.path.basename(bar_fig(res, i)))
