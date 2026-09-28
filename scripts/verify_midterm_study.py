#!/usr/bin/env python3
"""Independent calculation and PDF checks for the midterm study."""

from decimal import Decimal
import json
from pathlib import Path

import fitz
import hashlib


ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"_out"/"midterm_20260928"


def main():
    data=json.loads((OUT/"analysis.json").read_text(encoding="utf-8"))
    import csv
    series={}
    for name in ("SP500","DGS10"):
        with (ROOT/"data"/"midterm_20260928"/"raw"/f"{name}.csv").open() as f:
            series[name]={r["observation_date"]:Decimal(r[name]) for r in csv.DictReader(f) if r[name] not in (".","")}
    checked=0
    for e in data["events"]:
        for h in (1,7,15):
            d=e["target_dates"][str(h)]; a=e["anchor"]
            sp=(series["SP500"][d]/series["SP500"][a]-1)*100
            y=(series["DGS10"][d]-series["DGS10"][a])*100
            assert abs(float(sp)-e["sp_returns"][str(h)]) < 1e-10
            assert abs(float(y)-e["yield_changes_bp"][str(h)]) < 1e-10
            checked += 2
    calc={"status":"pass","independent_decimal_values":checked,"events":len(data["events"]),"horizons":[1,7,15]}
    (OUT/"calculation_verification.json").write_text(json.dumps(calc,indent=2),encoding="utf-8")

    pdf=fitz.open(OUT/"midterm_report.pdf"); assert len(pdf)==6
    text="\n".join(p.get_text() for p in pdf)
    for phrase in ("미국 중간선거","2018","2022","S&P 500","DGS10","관찰 데이터만으로 원인 특정 불가","투자 의견 아님"):
        assert phrase in text, phrase
    pages=OUT/"pages"; pages.mkdir(exist_ok=True)
    sizes=[]
    for i,p in enumerate(pdf):
        pix=p.get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False); path=pages/f"page_{i+1}.png"; pix.save(path); sizes.append(path.stat().st_size)
    fonts=sorted({f[3] for p in pdf for f in p.get_fonts(full=True)})
    report={"status":"pass","pages":len(pdf),"text_chars":len(text),"fonts":fonts,"render_bytes":sizes,"a4":all(abs(p.rect.width-595.276)<1 and abs(p.rect.height-841.89)<1 for p in pdf)}
    assert report["a4"] and min(sizes)>20000
    published=ROOT/"reports"/"midterm_20260928"/"us_midterm_opposition_win_market_study_ko.pdf"
    digest=lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert published.is_file() and digest(published)==digest(OUT/"midterm_report.pdf")
    report["published_pdf"] = str(published.relative_to(ROOT))
    report["published_sha256"] = digest(published)
    (OUT/"report_verification.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"calculation":calc,"report":report},ensure_ascii=False,indent=2))


if __name__=="__main__": main()
