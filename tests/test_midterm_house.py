import unittest
from datetime import date
from decimal import Decimal

from scripts.analyze_midterm_house import event_path


class MidtermHouseCalculations(unittest.TestCase):
    def setUp(self):
        self.series = [(date(2020, 1, i), Decimal(i)) for i in range(1, 20)]

    def test_next_observation_is_day_one(self):
        result = event_path(self.series, date(2020, 1, 1), "price")
        self.assertEqual(result["observations"]["1"]["date"], "2020-01-02")
        self.assertEqual(Decimal(result["observations"]["1"]["metric"]), Decimal(100))

    def test_yield_is_converted_to_basis_points(self):
        result = event_path(self.series, date(2020, 1, 1), "yield")
        self.assertEqual(Decimal(result["observations"]["7"]["metric"]), Decimal(700))

    def test_horizon_counts_valid_observations(self):
        sparse = self.series[:2] + self.series[3:]
        result = event_path(sparse, date(2020, 1, 1), "price")
        self.assertEqual(result["observations"]["7"]["date"], "2020-01-09")


if __name__ == "__main__":
    unittest.main()
