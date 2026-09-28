import importlib.util
import unittest
from pathlib import Path

import pandas as pd


SPEC = importlib.util.spec_from_file_location("midterm", Path(__file__).parents[1] / "scripts" / "analyze_midterm_study.py")
midterm = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(midterm)


class MidtermStudyTests(unittest.TestCase):
    def test_max_drawdown_excludes_pre_anchor_high(self):
        path = pd.Series([100.0, 110.0, 88.0, 99.0])
        self.assertAlmostEqual(midterm.max_drawdown(path), -20.0)

    def test_horizons_are_requested_trading_days(self):
        self.assertEqual(midterm.HORIZONS, (1, 7, 15))

    def test_event_definition_has_only_completed_flips(self):
        self.assertEqual([e["year"] for e in midterm.EVENTS], [2018, 2022])
        self.assertTrue(all(e["chamber"] == "하원" for e in midterm.EVENTS))


if __name__ == "__main__":
    unittest.main()
