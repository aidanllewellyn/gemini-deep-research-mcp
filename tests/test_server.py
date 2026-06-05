import importlib
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.pop("GOOGLE_API_KEY", None)
os.environ["GEMINI_API_KEY"] = "test-key"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["MCP_TRANSPORT"] = "stdio"
os.environ["MCP_DB_PATH"] = str(Path(tempfile.mkdtemp()) / "jobs.db")

server = importlib.import_module("server")


class FakeInteractions:
    def __init__(self):
        self.create_kwargs = None

    def create(self, **kwargs):
        self.create_kwargs = kwargs
        return SimpleNamespace(id="int_test", status="in_progress")


class ServerTest(unittest.TestCase):
    def test_research_start_schema_exposes_cost_aware_args(self):
        params = inspect.signature(server.research_start).parameters

        for name in [
            "research_mode",
            "budget_profile",
            "output_schema",
            "word_cap",
            "source_budget",
            "avoid_source_types",
            "prefer_source_types",
            "required_sections",
            "decision_schema_required",
            "cost_guardrail",
            "response_format",
        ]:
            self.assertIn(name, params)

    def test_prompt_wrapper_includes_alpha_controls(self):
        prompt = server._build_alpha_prompt(
            prompt="Rank destination wedding locations.",
            research_mode="screening",
            budget_profile="balanced",
            word_cap=1500,
            source_budget={"max_sources": 12, "max_searches": 8},
            decision_schema_required=True,
        )

        self.assertIn(server.ALPHA_MARKER, prompt)
        self.assertIn("Output cap: 1500 words", prompt)
        self.assertIn('"max_sources": 12', prompt)
        self.assertIn("Short markdown memo", prompt)
        self.assertIn("JSON-style decision object", prompt)
        self.assertIn(
            "Whether a Max run is justified and exactly what it should investigate", prompt
        )
        self.assertIn("decision_value", prompt)
        self.assertIn("<<<\nRank destination wedding locations.\n>>>", prompt)

    def test_plain_prompt_auto_wraps(self):
        prompt, meta = server._resolve_alpha_prompt(
            prompt="Rank destination wedding locations.",
            tier="standard",
        )

        self.assertTrue(meta["alpha_schema_applied"])
        self.assertIn(server.ALPHA_MARKER, prompt)
        self.assertEqual(meta["inferred_research_mode"], "screening")
        self.assertEqual(meta["budget_profile"], "balanced")
        self.assertEqual(meta["applied_word_cap"], 2500)
        self.assertEqual(meta["applied_source_budget"]["max_sources"], 14)
        self.assertTrue(meta["decision_schema_required"])

    def test_infer_research_modes(self):
        self.assertEqual(
            server.infer_research_mode("Need a vendor list with phone numbers"), "outreach_pack"
        )
        self.assertEqual(
            server.infer_research_mode("Deep dive with actual venues and pricing"), "deep_dive"
        )
        self.assertEqual(
            server.infer_research_mode("Build a competitor landscape"), "competitive_map"
        )
        self.assertEqual(
            server.infer_research_mode("Due diligence on regulatory high stakes risk"),
            "due_diligence",
        )
        self.assertEqual(server.infer_research_mode("Compare options and rank them"), "screening")

    def test_opt_out_skips_wrapper(self):
        prompt, meta = server._resolve_alpha_prompt(
            prompt="Raw research prompt",
            tier="standard",
            cost_guardrail={"disable_alpha_wrapper": True},
        )

        self.assertEqual(prompt, "Raw research prompt")
        self.assertFalse(meta["alpha_schema_applied"])

    def test_wrapper_is_idempotent(self):
        original = f"{server.ALPHA_MARKER}\nAlready wrapped"
        prompt, meta = server._resolve_alpha_prompt(prompt=original, tier="standard")

        self.assertEqual(prompt, original)
        self.assertFalse(meta["alpha_schema_applied"])

    def test_explicit_params_are_preserved(self):
        prompt, meta = server._resolve_alpha_prompt(
            prompt="Compare options.",
            tier="standard",
            word_cap=777,
            source_budget={"max_sources": 3, "max_searches": 2, "max_generic_sources": 0},
            prefer_source_types=["primary only"],
            avoid_source_types=["forums"],
            decision_schema_required=False,
        )

        self.assertEqual(meta["applied_word_cap"], 777)
        self.assertEqual(
            meta["applied_source_budget"],
            {"max_sources": 3, "max_searches": 2, "max_generic_sources": 0},
        )
        self.assertFalse(meta["decision_schema_required"])
        self.assertIn("primary only", prompt)
        self.assertIn("forums", prompt)

    def test_budget_profile_modifies_caps(self):
        _, lean = server._resolve_alpha_prompt(
            prompt="Compare options.",
            tier="standard",
            budget_profile="lean",
        )
        _, thorough = server._resolve_alpha_prompt(
            prompt="Compare options.",
            tier="standard",
            budget_profile="thorough",
        )

        self.assertEqual(lean["applied_word_cap"], 1750)
        self.assertEqual(lean["applied_source_budget"]["max_sources"], 10)
        self.assertEqual(lean["applied_source_budget"]["max_searches"], 6)
        self.assertEqual(thorough["applied_word_cap"], 3750)
        self.assertEqual(thorough["applied_source_budget"]["max_sources"], 21)
        self.assertEqual(thorough["applied_source_budget"]["max_searches"], 12)

    def test_max_defaults_to_thorough_budget(self):
        _, meta = server._resolve_alpha_prompt(
            prompt="Compare options.",
            tier="max",
        )

        self.assertEqual(meta["budget_profile"], "thorough")
        self.assertEqual(meta["applied_word_cap"], 3750)

    def test_legacy_research_start_still_requires_confirmation(self):
        result = server.research_start(
            prompt="Research topic",
            tier="standard",
            user_confirmed=False,
        )

        self.assertEqual(result["error"], "user_confirmation_required")
        self.assertIn("standard", result["tier_options"])
        self.assertIn("max", result["tier_options"])

    def test_research_start_passes_response_format_when_requested(self):
        fake_interactions = FakeInteractions()
        fake_gemini = SimpleNamespace(interactions=fake_interactions)
        response_format = {
            "type": "text",
            "mime_type": "application/json",
            "schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
        }

        with patch.object(server, "get_gemini_client", return_value=fake_gemini):
            result = server.research_start(
                prompt="Summarize this.",
                tier="standard",
                user_confirmed=True,
                research_mode="screening",
                budget_profile="balanced",
                word_cap=500,
                decision_schema_required=True,
                response_format=response_format,
            )

        self.assertEqual(result["interaction_id"], "int_test")
        self.assertEqual(fake_interactions.create_kwargs["response_format"], response_format)
        self.assertIn(server.ALPHA_MARKER, fake_interactions.create_kwargs["input"])
        self.assertTrue(result["alpha_metadata"]["alpha_schema_applied"])
        self.assertTrue(result["alpha_metadata"]["response_format_passthrough_used"])

    def test_research_start_reports_missing_api_key_without_calling_api(self):
        old_key = os.environ.pop("GEMINI_API_KEY", None)
        server._gemini_client = None
        try:
            result = server.research_start(
                prompt="Summarize this.",
                tier="standard",
                user_confirmed=True,
            )
        finally:
            if old_key is not None:
                os.environ["GEMINI_API_KEY"] = old_key

        self.assertEqual(result["status"], "error")
        self.assertIn("GEMINI_API_KEY", result["error"])
        self.assertIn("Set GEMINI_API_KEY", result["hint"])

    def test_get_gemini_client_is_lazy_and_cached(self):
        server._gemini_client = None
        fake_client = SimpleNamespace(interactions=SimpleNamespace())

        with patch.object(server.genai, "Client", return_value=fake_client) as client_ctor:
            first = server.get_gemini_client()
            second = server.get_gemini_client()

        self.assertIs(first, fake_client)
        self.assertIs(second, fake_client)
        client_ctor.assert_called_once_with(api_key="test-key")

    def test_exhaustive_profile_requires_max_confirmation(self):
        result = server.research_start(
            prompt="Research topic",
            tier="standard",
            user_confirmed=True,
            budget_profile="exhaustive",
        )

        self.assertEqual(result["error"], "max_confirmation_required")

    def test_extract_interaction_text_supports_legacy_outputs(self):
        interaction = SimpleNamespace(
            outputs=[
                SimpleNamespace(type="google_search_call", text="ignored"),
                SimpleNamespace(type="text", text="legacy report"),
            ]
        )

        self.assertEqual(server._extract_interaction_text(interaction), "legacy report")

    def test_extract_interaction_text_supports_new_steps(self):
        interaction = SimpleNamespace(
            steps=[
                SimpleNamespace(type="google_search_call", arguments={"queries": ["x"]}),
                SimpleNamespace(type="google_search_result", result={"search_suggestions": "..."}),
                SimpleNamespace(
                    type="model_output",
                    content=[SimpleNamespace(type="text", text="new steps report")],
                ),
            ]
        )

        self.assertEqual(server._extract_interaction_text(interaction), "new steps report")

    def test_pick_int_takes_first_numeric_alias(self):
        usage = {"prompt_token_count": 1234, "candidates_token_count": 56}
        # Aliases are tried in order; the first numeric match wins.
        self.assertEqual(server._pick_int(usage, "input_tokens", "prompt_token_count"), 1234)
        self.assertEqual(server._pick_int(usage, "output_tokens", "candidates_token_count"), 56)
        # No alias present → 0, never KeyError.
        self.assertEqual(server._pick_int(usage, "missing", "also_missing"), 0)
        # Non-numeric values are skipped.
        self.assertEqual(server._pick_int({"x": "not a number", "y": 7}, "x", "y"), 7)

    def test_estimate_cost_precise_breaks_out_cached_and_output(self):
        usage = {
            "input_tokens": 100_000,
            "cached_content_token_count": 40_000,
            "output_tokens": 10_000,
            "thoughts_token_count": 4_000,
        }
        cost = server._estimate_cost(usage)

        # 60k uncached input @ $2/M + 40k cached @ $0.20/M + 10k output @ $12/M
        self.assertEqual(cost["pricing_tier"], "standard (<=200k input)")
        self.assertEqual(cost["breakdown"]["input_uncached"]["tokens"], 60_000)
        self.assertEqual(cost["breakdown"]["input_cached"]["tokens"], 40_000)
        self.assertAlmostEqual(cost["estimated_total"], 0.248, places=3)

    def test_estimate_cost_uses_large_tier_above_200k(self):
        cost = server._estimate_cost({"input_tokens": 250_000, "output_tokens": 1_000})
        self.assertEqual(cost["pricing_tier"], "large (>200k input)")
        self.assertEqual(cost["breakdown"]["input_uncached"]["rate_per_M"], 4.00)

    def test_estimate_cost_falls_back_to_blended_rate_on_total_only(self):
        cost = server._estimate_cost({"total_tokens": 1_000_000})
        self.assertEqual(cost["mode"], "fallback_blended")
        self.assertEqual(cost["total_tokens"], 1_000_000)
        low, high = cost["estimated_range_usd"]
        self.assertLess(low, high)

    def test_estimate_cost_handles_empty_usage(self):
        self.assertIsNone(server._estimate_cost(None))
        self.assertIsNone(server._estimate_cost({}))


if __name__ == "__main__":
    unittest.main()
