#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python scripts/prepare_midterm_house.py
python scripts/analyze_midterm_house.py
python scripts/report_midterm_house.py
python scripts/verify_midterm_house.py

printf '\nPDF created: %s\n' "$(pwd)/_out/midterm_house_20260928/midterm_house_report.pdf"
