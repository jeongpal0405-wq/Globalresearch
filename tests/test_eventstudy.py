"""Synthetic calculation checks; no production data or network access.

These tests do not validate source selection, vintage handling, user
clarification, or report generation. See docs/VALIDATION.md for those cases.
"""

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd


def load_calculator():
    # Isolate the pure calculator from the legacy yfinance adapter.
    prices_stub = types.ModuleType("prices")

    def no_price_fetch(*args, **kwargs):
        raise AssertionError("Price fetching is forbidden in synthetic tests")

    prices_stub.get = no_price_fetch
    path = Path(__file__).resolve().parents[1] / "scripts" / "eventstudy.py"
    spec = importlib.util.spec_from_file_location("eventstudy_under_test", path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"prices": prices_stub}):
        spec.loader.exec_module(module)
    return module


class EventStudyCalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.es = load_calculator()

    def setUp(self):
        self.prices = pd.Series(
            [50.0, 100.0, 101.0, 99.0, 102.0, 104.0, 105.0],
            index=pd.to_datetime([
                "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07",
                "2025-01-08", "2025-01-09", "2025-01-10",
            ]),
        )
        self.release = "2025-01-03"

    def test_n01_return_starts_at_release_close(self):
        self.assertAlmostEqual(self.es.forward(self.prices, self.release, 1), 1.0)

    def test_n02_horizon_counts_trading_days(self):
        self.assertAlmostEqual(self.es.forward(self.prices, self.release, 5), 5.0)

    def test_n03_incomplete_horizon_preserves_short_return(self):
        self.assertTrue(np.isnan(self.es.forward(self.prices, self.release, 20)))
        self.assertAlmostEqual(self.es.forward(self.prices, self.release, 1), 1.0)

    def test_n04_drawdown_excludes_pre_event_peak(self):
        path = pd.Series(
            [200.0, 100.0, 110.0, 88.0, 99.0], index=self.prices.index[:5]
        )
        self.assertAlmostEqual(self.es.max_drawdown(path, self.release, 3), -20.0)

    def test_n05_summary_uses_valid_observations(self):
        stats = self.es.summarize([3.0, -1.0, np.nan, 0.0])
        self.assertEqual(stats["n"], 3)
        self.assertAlmostEqual(stats["mean"], 2.0 / 3.0)
        self.assertAlmostEqual(stats["median"], 0.0)
        self.assertAlmostEqual(stats["win"], 100.0 / 3.0)

    def test_n06_baseline_uses_complete_windows(self):
        path = pd.Series(
            [100.0, 110.0, 121.0],
            index=pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-08"]),
        )
        row = self.es.baseline(
            {"SYNTHETIC": path}, "2025-01-06", "2025-01-08", [1]
        ).iloc[0]
        self.assertEqual(row["n"], 2)
        self.assertAlmostEqual(row["mean"], 10.0)
        self.assertAlmostEqual(row["median"], 10.0)
        self.assertAlmostEqual(row["win"], 100.0)


if __name__ == "__main__":
    unittest.main()
