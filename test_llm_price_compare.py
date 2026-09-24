import unittest

from llm_price_compare import blended_cost, load_models


class TestPrices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_models()
        cls.models = {m["id"]: m for m in cls.data["models"]}

    def test_all_prices_nonnegative(self):
        for m in self.data["models"]:
            self.assertGreaterEqual(m["input"], 0)
            self.assertGreaterEqual(m["output"], 0)

    def test_blended_cost_math(self):
        m = {"input": 2.0, "output": 6.0}
        self.assertAlmostEqual(blended_cost(m, 1_000_000, 0), 2.0)
        self.assertAlmostEqual(blended_cost(m, 0, 1_000_000), 6.0)
        self.assertAlmostEqual(blended_cost(m, 500_000, 250_000), 2.5)

    def test_free_model_costs_zero(self):
        free = self.models["moonshotai/kimi-k3:free"]
        self.assertEqual(blended_cost(free, 10_000_000, 10_000_000), 0)

    def test_cheaper_than_kimi(self):
        cheap = min(self.data["models"], key=lambda m: m["input"])
        self.assertLess(cheap["input"], self.models["kimi-k3"]["input"])


if __name__ == "__main__":
    unittest.main()
