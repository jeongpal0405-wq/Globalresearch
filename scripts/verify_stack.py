# -*- coding: utf-8 -*-
"""PDF 보고서 스택 검증.

matplotlib(한글) -> Jinja2 HTML -> Playwright PDF -> PyMuPDF 텍스트 추출까지
한 번 관통시켜, 한글 폰트/마이너스 부호/면 분리가 정상인지 확인한다.

실행: py -3 scripts/verify_stack.py
산출: _out/verify_stack.pdf
"""
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from jinja2 import Template
from playwright.sync_api import sync_playwright
import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_out")
os.makedirs(OUT, exist_ok=True)


def as_url(path):
    return "file:///" + path.replace("\\", "/")


# 1) 한글 차트 (마이너스 부호 포함)
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(4, 2.4), dpi=150)
ax.bar(["1일", "5일", "20일"], [-1.24, 0.87, -3.05], color="#1f4e79")
ax.axhline(0, color="black", lw=0.8)
ax.set_title("포워드 수익률 중앙값")
ax.set_ylabel("수익률 (%)")
fig.tight_layout()
png = os.path.join(OUT, "verify_fig1.png")
fig.savefig(png)
plt.close(fig)

# 2) HTML (A4 3면, 2열 그림 배치)
html = Template("""
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 18mm 16mm; }
  body { font-family: "Malgun Gothic"; font-size: 10pt; line-height: 1.6; }
  h1 { font-size: 15pt; border-bottom: 2px solid #1f4e79; padding-bottom: 4px; }
  .page-break { page-break-after: always; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10mm; }
  .src { font-size: 8pt; color: #666; }
</style>
<h1>이벤트 스터디 — 스택 검증</h1>
<p>▶ 조건 정의<br>미국 CPI가 컨센서스를 +0.20%p 이상 상회한 날. 표본 n=5로 통계적 유의성 없음.</p>
<div class="page-break"></div>
<h1>그림</h1>
<div class="grid">
  <div><img src="{{ png }}" width="100%"><div class="src">자료: Investing.com, 자체 계산</div></div>
  <div><img src="{{ png }}" width="100%"><div class="src">자료: Yahoo Finance, 자체 계산</div></div>
</div>
<div class="page-break"></div>
<h1>데이터 및 통계 한계 고지</h1>
<p>윈도우 중첩으로 유효 표본은 명목보다 작음. 컨센서스 출처는 Investing.com.</p>
""").render(png=as_url(png))

html_path = os.path.join(OUT, "verify_stack.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

# 3) PDF
pdf_path = os.path.join(OUT, "verify_stack.pdf")
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(as_url(html_path))
    page.pdf(path=pdf_path, format="A4", print_background=True)
    browser.close()

# 4) 검증 — 눈으로 보지 않고 텍스트를 추출해 확인
doc = fitz.open(pdf_path)
text = "".join(pg.get_text() for pg in doc)

checks = {
    "면 수 3": doc.page_count == 3,
    "한글 정상": "이벤트 스터디" in text and "컨센서스" in text,
    "면 분리 정상": "한계 고지" in doc[2].get_text(),
}
for name, ok in checks.items():
    print(("PASS  " if ok else "FAIL  ") + name)
print("PDF:", pdf_path)

sys.exit(0 if all(checks.values()) else 1)
