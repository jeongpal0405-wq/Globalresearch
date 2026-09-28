#!/usr/bin/env python3
"""Build the Korean A4 PDF for the post-midterm House-control study."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_out" / "midterm_house_20260928"
FONT_DIR = ROOT / "data" / "midterm_house_20260928" / "fonts"


def register_fonts() -> None:
    regular = FONT_DIR / "NotoSansCJKkr-Regular.otf"
    bold = FONT_DIR / "NotoSansCJKkr-Bold.otf"
    if not regular.exists() or not bold.exists():
        raise FileNotFoundError("Download the Noto Sans CJK KR regular and bold fonts into the study font directory")
    pdfmetrics.registerFont(TTFont("NotoKR", regular))
    pdfmetrics.registerFont(TTFont("NotoKRBold", bold))


def fmt(value: str, suffix: str) -> str:
    return f"{float(value):+.1f}{suffix}"


def make_table(data, widths=None, header=True):
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), "NotoKR"), ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("LEADING", (0, 0), (-1, -1), 11), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#b8c2cc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#15324b")),
                     ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 0), "NotoKRBold")]
    for row in range(1 if header else 0, len(data)):
        if row % 2 == 0:
            commands.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#eef3f6")))
    table.setStyle(TableStyle(commands))
    return table


def main() -> None:
    register_fonts()
    analysis = json.loads((OUT / "analysis.json").read_text(encoding="utf-8"))
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleKR", parent=styles["Title"], fontName="NotoKRBold", fontSize=20, leading=28, textColor=colors.HexColor("#15324b"), spaceAfter=12)
    h1 = ParagraphStyle("H1KR", parent=styles["Heading1"], fontName="NotoKRBold", fontSize=14, leading=20, textColor=colors.HexColor("#15324b"), spaceBefore=8, spaceAfter=8)
    body = ParagraphStyle("BodyKR", parent=styles["BodyText"], fontName="NotoKR", fontSize=9.4, leading=15, spaceAfter=7)
    note = ParagraphStyle("NoteKR", parent=body, fontSize=8, leading=12, textColor=colors.HexColor("#425466"))
    doc = SimpleDocTemplate(str(OUT / "midterm_house_report.pdf"), pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=16*mm, bottomMargin=16*mm,
                            title="미국 중간선거 하원 탈환 이후 시장 성과", author="Globalresearch")
    story = [Paragraph("미국 중간선거: 야당의 하원 탈환 이후 시장 성과", title),
             Paragraph("2015년 이후 · 미국채 10년물 금리 변화와 S&amp;P 500 가격수익률", h1),
             Paragraph("요약", h1),
             Paragraph("해당 사례는 2018년 민주당과 2022년 공화당의 하원 탈환, 총 2건이다. 두 사례 평균으로 10년물 금리는 1·7·15거래일 뒤 각각 1.0bp·23.0bp·40.0bp 하락했다. S&amp;P 500 평균 가격수익률은 각각 0.0%·+1.1%·+3.1%였다.", body),
             Paragraph("표본이 2건뿐이고 방향도 S&amp;P 500에서는 사례별로 엇갈린다. 이 결과는 조건부 과거 경로의 기술통계이며, 선거 결과의 인과효과나 통계적 유의성을 뜻하지 않는다.", body),
             Paragraph("확정 기준", h1),
             make_table([["항목", "적용 기준"], ["모집단", "2015년 이후 2022년까지의 정기 미국 중간선거"], ["사건", "대통령 야당이 하원 과반을 대통령 여당에서 탈환"], ["기산/구간", "선거일 값을 0일로 하고 다음 유효 관측치를 1일로 한 1·7·15거래일"], ["미 국채", "FRED DGS10 금리 변화폭, bp"], ["주식", "FRED SP500 가격지수 수익률, 배당 제외"]], [34*mm, 142*mm]),
             Spacer(1, 5*mm), Paragraph("핵심 결과", h1)]
    summary_rows = [["자산", "1일 평균", "7일 평균", "15일 평균", "상승 비율(1/7/15일)"]]
    summary_rows.append(["미국채 10년 금리", *[fmt(analysis["summary"]["dgs10"][str(h)]["mean"], "bp") for h in (1,7,15)], "0% / 0% / 0%"])
    summary_rows.append(["S&P 500", *[fmt(analysis["summary"]["sp500"][str(h)]["mean"], "%") for h in (1,7,15)], "50% / 50% / 50%"])
    story += [make_table(summary_rows, [38*mm, 25*mm, 25*mm, 25*mm, 52*mm]), PageBreak(),
              Paragraph("사례별 성과", title)]
    for case in analysis["cases"]:
        story += [Paragraph(f"{case['year']}년: {case['winner']}당 하원 탈환 ({case['house_seats']})", h1),
                  Paragraph(f"선거일 {case['election_date']} · 대통령 소속 정당 {case['president_party']}당", body)]
        rows = [["자산", "0일 값", "1거래일", "7거래일", "15거래일"]]
        rows.append(["10년물 금리", f"{float(case['dgs10']['base_value']):.2f}%", *[fmt(case["dgs10"]["observations"][str(h)]["metric"], "bp") for h in (1,7,15)]])
        rows.append(["S&P 500", f"{float(case['sp500']['base_value']):,.2f}", *[fmt(case["sp500"]["observations"][str(h)]["metric"], "%") for h in (1,7,15)]])
        story += [make_table(rows, [36*mm, 31*mm, 31*mm, 31*mm, 31*mm]), Spacer(1, 4*mm)]
        dates = [["구간", "10년물 관측일", "S&P 500 관측일"]]
        for h in (1,7,15):
            dates.append([f"{h}거래일", case["dgs10"]["observations"][str(h)]["date"], case["sp500"]["observations"][str(h)]["date"]])
        story += [make_table(dates, [40*mm, 60*mm, 60*mm]), Spacer(1, 7*mm)]
    story += [Paragraph("금리와 주식의 거래일 달력이 달라 2018년 재향군인의 날 및 2022년 추수감사절 등의 영향으로 동일 순번의 관측일이 다를 수 있다. 각 계열에서 값이 존재하는 유효 관측치를 거래일로 세었다.", note),
              PageBreak(), Paragraph("비교 기준과 해석", title), Paragraph("전체 거래일 비교", h1)]
    baseline_rows = [["자산/구간", "표본 n", "평균", "중앙값", "양(+) 비율"]]
    for asset, label, suffix in (("dgs10","10년 금리","bp"),("sp500","S&P 500","%")):
        for h in (1,7,15):
            b=analysis["baseline"][asset][str(h)]
            baseline_rows.append([f"{label} {h}일", str(b["n"]), fmt(b["mean"],suffix), fmt(b["median"],suffix), f"{float(b['positive_pct']):.1f}%"])
    story += [make_table(baseline_rows, [43*mm, 25*mm, 30*mm, 30*mm, 32*mm]),
              Paragraph("비교군은 2018-11-06부터 2022-11-30까지 각 FRED 계열의 모든 유효 관측일에서 만든 중첩 허용 이동 구간이다. 선거 사례와 동일한 보유기간 정의지만 계절·거시환경을 통제한 대조군은 아니다.", note),
              Paragraph("관찰", h1),
              Paragraph("두 선거 뒤 10년 금리는 7일과 15일 구간에서 모두 하락했다. 하락폭은 2022년(-32bp, -61bp)이 2018년(-14bp, -19bp)보다 컸다. 반면 S&amp;P 500은 2018년에 1일 상승 후 7·15일에는 선거일 아래였고, 2022년에는 1일 하락 후 7·15일에 반등했다. 따라서 주식 경로에 공통된 단기 방향은 관찰되지 않는다.", body),
              Paragraph("두 사례의 평균만 보면 장기 구간에서 금리 하락과 주가 상승이 함께 나타나지만, 표본 수가 2이므로 일반화할 수 없다. 통화정책 기대, 물가 발표 등 동시 요인을 분리하지 않았으므로 관측 데이터만으로 원인 특정 불가하다.", body),
              PageBreak(), Paragraph("출처·방법·한계", title), Paragraph("출처", h1),
              Paragraph("① 미국 하원 역사가실, Election Statistics, 2018 및 2022 공식 선거통계 PDF. ② 미국 하원 역사가실, Party Divisions of the House of Representatives, 116대 235D–199R 및 118대 213D–222R. ③ Federal Reserve Bank of St. Louis FRED, DGS10 및 SP500 일별 계열. 원본은 2026-09-28 수집해 해시와 함께 보존했다.", body),
              Paragraph("방법", h1),
              Paragraph("원 정밀도의 Decimal 산술로 계산하고 표시 단계에서만 소수점 첫째 자리로 반올림했다. 금리 변화는 (관측금리−선거일금리)×100bp, 주가 수익률은 (관측지수/선거일지수−1)×100이다. 결측은 0으로 대체하지 않았다.", body),
              Paragraph("한계", h1),
              Paragraph("분석 종료일을 2022년 말로 두었으므로 2015년 이후 완료된 정기 중간선거는 2018·2022년 두 번뿐이며 둘 다 야당의 하원 탈환이었다. 최종 의석 결과에 따른 사후 분류로서 결과가 시장에 확정된 시점을 기산일로 삼은 분석이 아니다. 표본 2건, 중첩 비교군, 수정 가능한 과거 계열, 배당 제외, 동시 사건 미통제가 주요 한계다. 투자 전망이나 매매 권고를 제공하지 않는다.", body)]

    def footer(canvas, document):
        canvas.saveState(); canvas.setFont("NotoKR", 7.5); canvas.setFillColor(colors.HexColor("#627386"))
        canvas.drawString(16*mm, 9*mm, "Globalresearch · 2026-09-28")
        canvas.drawRightString(A4[0]-16*mm, 9*mm, f"{document.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT / "midterm_house_report.pdf")


if __name__ == "__main__":
    main()
