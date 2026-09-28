#!/usr/bin/env python3
"""Create the Korean A4 PDF for the midterm study."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageBreak, PageTemplate,
                               Paragraph, Spacer, Table, TableStyle)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_out" / "midterm_20260928"
PUBLISHED = ROOT / "reports" / "midterm_20260928" / "us_midterm_opposition_win_market_study_ko.pdf"
FONT_DIR = ROOT / "tmp" / "midterm_20260928"
BLUE, NAVY, RED, GREY, LIGHT = "#3478F6", "#15253B", "#E65D4F", "#596579", "#EDF2F7"


def fmt(v, unit="%"):
    return f"{v:+.1f}{unit}"


def make_charts(data):
    font_path = FONT_DIR / "NanumGothic-Regular.ttf"
    font_manager.fontManager.addfont(font_path)
    plt.rcParams.update({"font.family": "NanumGothic", "axes.unicode_minus": False})
    years = [str(e["year"]) for e in data["events"]]
    hs = [1, 7, 15]
    for kind, title, unit, key, colorset in [
        ("sp500", "S&P 500 선거 후 수익률", "%", "sp_returns", [BLUE, NAVY]),
        ("dgs10", "미국채 10년물 금리 변화", "bp", "yield_changes_bp", [RED, "#9C3D54"]),
    ]:
        fig, ax = plt.subplots(figsize=(7.2, 3.5))
        x = range(len(hs)); width = .34
        for j, event in enumerate(data["events"]):
            vals = [event[key][str(h)] for h in hs]
            xx = [i + (j - .5) * width for i in x]
            ax.bar(xx, vals, width=width, label=years[j], color=colorset[j])
            for xi, val in zip(xx, vals):
                ax.text(xi, val + (0.5 if val >= 0 else -0.5), fmt(val, unit), ha="center",
                        va="bottom" if val >= 0 else "top", fontsize=8)
        ax.axhline(0, color="#7A8699", lw=.8)
        ax.set_xticks(list(x), [f"+{h}거래일" for h in hs])
        ax.set_ylabel(unit); ax.set_title(title, loc="left", fontweight="bold")
        ax.legend(frameon=False, ncol=2); ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.18); fig.tight_layout()
        fig.savefig(OUT / f"{kind}_bars.png", dpi=180, transparent=False); plt.close(fig)


def styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", fontName="NanumBold", fontSize=24, leading=32, textColor=colors.HexColor(NAVY)),
        "h1": ParagraphStyle("h1", fontName="NanumBold", fontSize=17, leading=22, textColor=colors.HexColor(NAVY), spaceAfter=8),
        "h2": ParagraphStyle("h2", fontName="NanumBold", fontSize=11, leading=15, textColor=colors.HexColor(BLUE), spaceBefore=7, spaceAfter=4),
        "body": ParagraphStyle("body", fontName="Nanum", fontSize=9.2, leading=15, textColor=colors.HexColor(NAVY)),
        "small": ParagraphStyle("small", fontName="Nanum", fontSize=7.5, leading=11, textColor=colors.HexColor(GREY)),
        "kpi": ParagraphStyle("kpi", fontName="NanumBold", fontSize=14, leading=18, alignment=TA_CENTER, textColor=colors.HexColor(NAVY)),
    }


def table(rows, widths=None, header=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    rules = [("FONTNAME", (0, 0), (-1, -1), "Nanum"), ("FONTSIZE", (0, 0), (-1, -1), 7.8),
             ("LEADING", (0, 0), (-1, -1), 11), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("GRID", (0, 0), (-1, -1), .3, colors.HexColor("#CBD5E1")),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if header:
        rules += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(NAVY)),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "NanumBold")]
    t.setStyle(TableStyle(rules)); return t


def footer(canvas, doc):
    canvas.saveState(); canvas.setFont("Nanum", 7); canvas.setFillColor(colors.HexColor(GREY))
    canvas.drawString(18 * mm, 11 * mm, "Global Research | 과거 사례 분석 · 투자 의견 아님")
    canvas.drawRightString(192 * mm, 11 * mm, f"{doc.page}")
    canvas.setStrokeColor(colors.HexColor("#D7DEE8")); canvas.line(18 * mm, 15 * mm, 192 * mm, 15 * mm)
    canvas.restoreState()


def build(data):
    pdfmetrics.registerFont(TTFont("Nanum", FONT_DIR / "NanumGothic-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("NanumBold", FONT_DIR / "NanumGothic-Bold.ttf"))
    make_charts(data); s = styles()
    doc = BaseDocTemplate(str(OUT / "midterm_report.pdf"), pagesize=A4,
                          leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=20*mm,
                          title="미국 중간선거 야당 다수당 탈환 이후 시장 성과")
    doc.addPageTemplates(PageTemplate(id="main", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="frame")], onPage=footer))
    story = []
    story += [Spacer(1, 18*mm), Paragraph("미국 중간선거<br/>야당의 의회 다수당 탈환 이후", s["title"]),
              Spacer(1, 4*mm), Paragraph("미국채 10년물 금리 변화 · S&P 500 가격수익률<br/>선거 다음 거래일 종가 기준 +1·+7·+15거래일", s["body"]),
              Spacer(1, 14*mm)]
    kpis = [[Paragraph("2건<br/><font size=8>2018·2022 전체 확정 사례</font>", s["kpi"]),
             Paragraph("하원 2건<br/><font size=8>상원 단독 탈환 사례 0건</font>", s["kpi"]),
             Paragraph("사후 분류<br/><font size=8>실시간 매매 검증 아님</font>", s["kpi"])]]
    kt = Table(kpis, colWidths=[doc.width/3]*3, rowHeights=[34*mm]); kt.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor(LIGHT)), ("BOX", (0,0), (-1,-1), .5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0,0), (-1,-1), .5, colors.white), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story += [kt, Spacer(1, 12*mm), Paragraph("핵심 결론", s["h1"]),
              Paragraph("두 사례에서 S&P 500의 +1·+7·+15거래일 방향은 모두 엇갈렸다. 2018년에는 세 구간 모두 하락했고 2022년에는 모두 상승했다. 10년물 금리는 두 사례 모두 +15거래일에 하락했다. 다만 표본이 2건뿐이고 동시 거시 요인을 통제하지 않았으므로 선거의 인과 효과로 해석할 수 없다.", s["body"]),
              Spacer(1, 8*mm), Paragraph("작성 2026-09-28 · 데이터 관측 종료: S&P 500 2026-09-25, DGS10 2026-09-24", s["small"]), PageBreak()]

    story += [Paragraph("1. 표본 선정과 사건 확인", s["h1"]),
              Paragraph("포함 조건은 2015년 이후 정기 중간선거에서 대통령 소속 정당이 아닌 정당이 하원 또는 상원 다수당 지위를 새로 획득한 경우다. 2018년 민주당과 2022년 공화당이 각각 하원을 탈환했다. 2026년 선거는 분석일 현재 아직 실시되지 않았다.", s["body"]), Spacer(1, 5*mm)]
    rows = [["선거", "대통령 여당", "야당 승자", "탈환", "직전 → 선거 결과"]]
    for e in data["events"]:
        rows.append([f'{e["year"]}-{e["election_date"][5:]}', e["president_party"], e["winner"], e["chamber"], f'{e["before"]} → {e["after"]}'])
    story += [table(rows, [25*mm, 26*mm, 24*mm, 18*mm, 81*mm]), Spacer(1, 8*mm),
              Paragraph("판정 근거", s["h2"]),
              Paragraph("미 하원 역사실의 의회별 프로필에 기재된 선거일 결과 기준 정당 의석을 직전 의회와 비교했다. 115대→116대는 공화당 다수에서 민주당 235석으로, 117대→118대는 민주당 다수에서 공화당 222석으로 바뀌었다. 공식 Election Statistics 색인은 2018·2022년 전체 선거 통계 원문을 제공한다.", s["body"]),
              Paragraph("주의: 최종 선거 결과로 사건을 사후 분류했다. 과반 확정 최초 시각이나 당시 거래 가능성은 검증하지 않았다.", s["small"]), PageBreak()]

    story += [Paragraph("2. 사례별 시장 성과", s["h1"])]
    rows = [["사례 / 기산일", "지표", "+1일", "+7일", "+15일", "15일 경로"]]
    for e in data["events"]:
        rows.append([f'{e["year"]} / {e["anchor"]}', "S&P 500", *[fmt(e["sp_returns"][str(h)]) for h in (1,7,15)], f'MDD {fmt(e["sp_mdd_15"])}'])
        rows.append(["", "DGS10", *[fmt(e["yield_changes_bp"][str(h)], "bp") for h in (1,7,15)], f'{fmt(e["yield_min_change_bp_15"], "bp")}~{fmt(e["yield_max_change_bp_15"], "bp")}'])
    story += [table(rows, [31*mm, 24*mm, 25*mm, 25*mm, 25*mm, 44*mm]), Spacer(1, 4*mm),
              Paragraph("S&P 500: P(t+h)/P(t)-1. DGS10: 금리(t+h)-금리(t), 1%p=100bp. MDD는 기산일을 포함한 종가 경로의 고점 대비 최대 하락률이다. 금리 변화에 가격수익률·쿠폰수익은 포함되지 않는다.", s["small"]),
              Spacer(1, 5*mm), Image(OUT / "sp500_bars.png", width=174*mm, height=84*mm), PageBreak(),
              Paragraph("3. 미국채 금리 변화와 관찰", s["h1"]), Image(OUT / "dgs10_bars.png", width=174*mm, height=84*mm), Spacer(1, 5*mm)]
    for e in data["events"]:
        story += [Paragraph(f'{e["year"]}년', s["h2"]),
                  Paragraph(f'기산일 금리는 {e["yield_anchor"]:.2f}%였다. +1·+7·+15거래일 변화는 각각 ' + ", ".join(fmt(e["yield_changes_bp"][str(h)], "bp") for h in (1,7,15)) + f'였다. 같은 15거래일 경로의 범위는 기산일 대비 {fmt(e["yield_min_change_bp_15"], "bp")}~{fmt(e["yield_max_change_bp_15"], "bp")}였다.', s["body"])]
    story += [Spacer(1, 6*mm), Paragraph("관찰 데이터만으로 원인 특정 불가", s["h2"]),
              Paragraph("금리와 주가에는 물가, 통화정책 기대, 경기·기업실적과 같은 동시 요인이 반영된다. 사건 발생과 이후 경로의 병치를 인과관계로 해석하지 않는다.", s["body"]), PageBreak()]

    story += [Paragraph("4. 전체 거래일 베이스라인", s["h1"]),
              Paragraph(f'FRED가 제공한 두 계열의 공통 분석 기반인 S&P 500 거래일 {data["baseline"]["range"][0]}~{data["baseline"]["range"][1]}에서 각 거래일을 출발점으로 동일 구간을 계산했다. 사건일도 포함하며 관찰 구간은 서로 중첩될 수 있다.', s["body"]), Spacer(1, 5*mm)]
    rows = [["지표", "구간", "n", "평균", "중앙값", "상승 비율"]]
    for asset, label, unit in [("sp500", "S&P 500", "%"), ("dgs10", "DGS10", "bp")]:
        for h in (1,7,15):
            x=data["baseline"][asset][str(h)]
            rows.append([label, f'+{h}일', f'{x["n"]:,}', fmt(x["mean"],unit), fmt(x["median"],unit), f'{x["positive_pct"]:.1f}%'])
    story += [table(rows, [30*mm, 24*mm, 28*mm, 30*mm, 30*mm, 32*mm]), Spacer(1, 5*mm),
              Paragraph("DGS10은 S&P 500 거래일의 시작·종료일 양쪽 금리가 모두 존재할 때만 포함했다. ‘상승 비율’은 변화가 0보다 큰 유효 사례의 비율이며 결측을 0으로 채우지 않았다.", s["small"]),
              Spacer(1, 8*mm), Paragraph("표본 평균", s["h2"])]
    mean_rows=[["지표", "+1일", "+7일", "+15일"]]
    for key,label,unit in [("sp_returns","S&P 500","%"),("yield_changes_bp","DGS10","bp")]:
        mean_rows.append([label]+[fmt(sum(e[key][str(h)] for e in data["events"])/2,unit) for h in (1,7,15)])
    story += [table(mean_rows,[42*mm]*4), Paragraph("n=2 평균은 극단적으로 불안정하다. 통계적 유의성 검정이나 일반화에는 사용하지 않았다.", s["small"]), PageBreak()]

    story += [Paragraph("5. 방법·출처·한계", s["h1"]),
              Paragraph("계산 절차", s["h2"]),
              Paragraph("선거일 다음 S&P 500 거래일 종가를 t=0으로 선택하고, 해당 거래일 열에서 +1·+7·+15번째 종가를 사용했다. 표시 전 원 정밀도로 계산했다. S&P 500은 배당 제외 가격지수이며 DGS10은 채권 투자 총수익이 아니라 시장수익률(금리)의 변화폭이다.", s["body"]),
              Paragraph("정량자료", s["h2"]),
              Paragraph("FRED API를 우선 호출했으나 이 환경에 API 키가 없어 HTTP 400을 기록했다. 동일 기관의 공식 FRED CSV 다운로드에서 SP500·DGS10 원시 관측값을 확보했으며 원본과 SHA-256을 보존했다. SP500 제공 시작일은 2016-09-26이다.", s["body"]),
              Paragraph("공식 출처", s["h2"]),
              Paragraph("• 미국 하원 역사실 Congress Profiles 115th·116th·117th·118th<br/>• 미국 하원 역사실 Election Statistics 색인 및 2018·2022 공식 통계<br/>• Federal Reserve Bank of St. Louis FRED: SP500, DGS10", s["body"]),
              Paragraph("제약", s["h2"]),
              Paragraph("① 확정 사례 2건의 매우 작은 표본 ② 최종 결과를 이용한 사후 분류 ③ 과반 확정 시각 미검증 ④ 거시·계절·정책 요인 미통제 ⑤ 가격·금리 관측값의 최초 게시 판본 미검증 ⑥ 베이스라인 구간 중첩 ⑦ DGS10은 채권 가격수익률이 아님. 따라서 예측·투자의견·인과 추론으로 사용할 수 없다.", s["body"]),
              Spacer(1, 8*mm), Paragraph("재현 파일", s["h2"]),
              Paragraph("_out/midterm_20260928/analysis.json · event_returns.csv · calculation_verification.json · report_verification.json", s["small"])]
    doc.build(story)
    PUBLISHED.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(OUT / "midterm_report.pdf", PUBLISHED)


if __name__ == "__main__":
    data=json.loads((OUT/"analysis.json").read_text(encoding="utf-8")); build(data)
