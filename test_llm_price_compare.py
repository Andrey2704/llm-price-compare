import json
import tempfile
import unittest
from pathlib import Path

from llm_price_compare import (
    blended_cost,
    data_age_days,
    filter_models,
    fmt_context,
    fmt_price,
    fmt_tokens,
    load_data,
    render_csv,
    render_json,
    render_table,
    sort_models,
    to_records,
    validate_data,
)


class TestPrices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_data()
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

    def test_validate_clean_data(self):
        self.assertEqual(validate_data(self.data), [])


class TestFormatting(unittest.TestCase):
    def test_fmt_price(self):
        self.assertEqual(fmt_price(0), "free")
        self.assertEqual(fmt_price(0.0042), "$0.0042")
        self.assertEqual(fmt_price(3), "$3.00")

    def test_fmt_tokens(self):
        self.assertEqual(fmt_tokens(1_000_000), "1 000 000")

    def test_fmt_context(self):
        self.assertEqual(fmt_context(128), "128K")
        self.assertEqual(fmt_context(1000), "1M")


class TestSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_data()
        cls.models = cls.data["models"]

    def test_free_filter(self):
        free = filter_models(self.models, free_only=True)
        self.assertTrue(free)
        self.assertTrue(all(m["free_tier"] for m in free))

    def test_provider_filter_is_case_insensitive(self):
        groq = filter_models(self.models, provider="groq")
        self.assertTrue(groq)
        self.assertTrue(all("groq" in m["provider"].lower() for m in groq))

    def test_query_filter_matches_id(self):
        hits = filter_models(self.models, query="kimi")
        self.assertGreaterEqual(len(hits), 2)

    def test_sort_by_input_ascending(self):
        ordered = sort_models(self.models, "input")
        prices = [m["input"] for m in ordered]
        self.assertEqual(prices, sorted(prices))

    def test_sort_by_context_descending(self):
        ordered = sort_models(self.models, "context")
        contexts = [m["context_k"] for m in ordered]
        self.assertEqual(contexts, sorted(contexts, reverse=True))

    def test_sort_by_blended_respects_volume(self):
        ordered = sort_models(self.models, "blended", in_tokens=1_000_000, out_tokens=0)
        costs = [blended_cost(m, 1_000_000, 0) for m in ordered]
        self.assertEqual(costs, sorted(costs))

    def test_unknown_sort_key_raises(self):
        with self.assertRaises(ValueError):
            sort_models(self.models, "nonsense")


class TestRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_data()
        cls.models = cls.data["models"][:3]

    def test_table_has_header_and_rows(self):
        table = render_table(self.models, 1_000_000, 500_000)
        lines = table.splitlines()
        self.assertIn("Модель", lines[0])
        self.assertEqual(len(lines), len(self.models) + 2)

    def test_csv_roundtrip(self):
        text = render_csv(to_records(self.models, 1_000_000, 500_000))
        header = text.splitlines()[0]
        self.assertIn("blended_usd", header)
        self.assertEqual(len(text.splitlines()), len(self.models) + 1)

    def test_json_is_parseable(self):
        payload = json.loads(
            render_json(to_records(self.models, 1_000_000, 0), {"count": 3})
        )
        self.assertEqual(payload["meta"]["count"], 3)
        self.assertEqual(len(payload["models"]), len(self.models))


class TestValidation(unittest.TestCase):
    def test_missing_field_reported(self):
        broken = {"models": [{"id": "x", "provider": "y", "input": 1, "output": 2}]}
        problems = validate_data(broken)
        self.assertTrue(any("context_k" in p for p in problems))

    def test_negative_price_reported(self):
        broken = {
            "models": [
                {
                    "id": "x",
                    "provider": "y",
                    "input": -1,
                    "output": 2,
                    "context_k": 8,
                }
            ]
        }
        problems = validate_data(broken)
        self.assertTrue(any("отрицательная" in p for p in problems))

    def test_duplicate_id_reported(self):
        model = {"id": "x", "provider": "y", "input": 1, "output": 1, "context_k": 8}
        problems = validate_data({"models": [model, dict(model)]})
        self.assertTrue(any("повторяющийся" in p for p in problems))

    def test_data_age(self):
        from datetime import date

        age = data_age_days({"updated": "2026-01-01"}, today=date(2026, 1, 31))
        self.assertEqual(age, 30)
        self.assertIsNone(data_age_days({}))


class TestLoadErrors(unittest.TestCase):
    def test_missing_models_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text('{"prices": []}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_data(path)


if __name__ == "__main__":
    unittest.main()
