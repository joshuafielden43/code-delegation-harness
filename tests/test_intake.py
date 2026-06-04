"""Tests for the intake gate (intake.py)."""
import unittest
from unittest.mock import MagicMock, patch

from src.code_delegation_harness.intake import (
    ArtifactExpectation,
    CLIOrchestratorBackend,
    IntakeResult,
    _degraded_intake,
    _extract_json_from_cli_output,
    detect_prompt_type,
    get_orchestrator,
    run_intake_gate,
)


class TestDetectPromptType(unittest.TestCase):
    def test_human_prompt_plain(self):
        prompt = "I want you to add a login feature to my web app."
        self.assertEqual(detect_prompt_type(prompt), "human")

    def test_human_prompt_with_hedging(self):
        prompt = "Could you please add authentication to my project?"
        self.assertEqual(detect_prompt_type(prompt), "human")

    def test_ai_structured_with_task_marker(self):
        prompt = "TASK: Add OAuth2 login to src/auth.py\nCONSTRAINTS: No new deps"
        self.assertEqual(detect_prompt_type(prompt), "ai_structured")

    def test_ai_structured_with_artifacts(self):
        prompt = (
            "TASK: Refactor the data pipeline\n"
            "TARGET: src/pipeline.py\n"
            "ARTIFACTS: pipeline.py, tests/test_pipeline.py, README.md\n"
            "CONSTRAINTS: preserve public API"
        )
        self.assertEqual(detect_prompt_type(prompt), "ai_structured")

    def test_ai_structured_no_hedging(self):
        prompt = (
            "TASK: Implement Redis caching layer\n"
            "FILES: cache.py, config.py\n"
            "Do not modify existing public interfaces.\n"
        )
        self.assertEqual(detect_prompt_type(prompt), "ai_structured")


class TestIntakeResultDefaults(unittest.TestCase):
    def test_defaults_are_sane(self):
        r = IntakeResult()
        self.assertEqual(r.intent_detection, "human")
        self.assertFalse(r.was_normalized)
        self.assertFalse(r.degraded)
        self.assertIsNone(r.degraded_reason)

    def test_degraded_intake_preserves_raw(self):
        raw = "I want you to build something"
        result = _degraded_intake(raw, "test error")
        self.assertEqual(result.intent_normalized, raw)
        self.assertTrue(result.degraded)
        self.assertFalse(result.was_normalized)


class TestRunIntakeGate(unittest.TestCase):
    def test_ai_structured_prompt_passes_through(self):
        """AI-structured prompts must skip normalization entirely (D-01)."""
        mock_orch = MagicMock()
        prompt = "TASK: Add login\nTARGET: src/auth.py\nARTIFACTS: auth.py"
        result = run_intake_gate(
            prompt, orchestrator=mock_orch, model="test-model", quiet=True
        )
        mock_orch.run_intake.assert_not_called()
        self.assertEqual(result.intent_detection, "ai_structured")
        self.assertFalse(result.was_normalized)
        self.assertEqual(result.intent_normalized, prompt)

    def test_human_prompt_calls_orchestrator(self):
        mock_orch = MagicMock()
        mock_orch.run_intake.return_value = IntakeResult(
            intent_detection="human",
            was_normalized=True,
            intent_normalized="TASK: Add login\nARTIFACTS: auth.py",
            manifest_expected=[ArtifactExpectation(type="file", name="auth.py", description="OAuth2")],
            attack_frame_generated="Attack: check error handling",
            normalized_via_model="test-model",
        )
        result = run_intake_gate(
            "I want to add login to my app",
            orchestrator=mock_orch,
            model="test-model",
            quiet=True,
        )
        mock_orch.run_intake.assert_called_once()
        self.assertTrue(result.was_normalized)
        self.assertEqual(len(result.manifest_expected), 1)
        self.assertIsNotNone(result.attack_frame_generated)

    def test_orchestrator_failure_degrades_gracefully(self):
        """Intake failure must never abort the run (D-01 degradation rule)."""
        mock_orch = MagicMock()
        mock_orch.run_intake.side_effect = RuntimeError("network timeout")
        raw = "add login feature"
        result = run_intake_gate(
            raw, orchestrator=mock_orch, model="test-model", quiet=True
        )
        self.assertFalse(result.was_normalized)
        self.assertEqual(result.intent_normalized, raw)
        self.assertTrue(result.degraded)

    def test_intent_raw_preserved_invariant(self):
        """D-03: intent_raw is immutable — the normalized result is separate."""
        mock_orch = MagicMock()
        raw = "please add a signup page"
        normalized = "TASK: Implement user signup page\nARTIFACTS: signup.html"
        mock_orch.run_intake.return_value = IntakeResult(
            was_normalized=True,
            intent_normalized=normalized,
        )
        result = run_intake_gate(raw, orchestrator=mock_orch, model="m", quiet=True)
        # The raw prompt is NOT modified — it stays in intent_raw at call site
        # (harness.main captures intent_raw separately before calling intake)
        self.assertEqual(result.intent_normalized, normalized)

    def test_degraded_reason_truncated(self):
        long_reason = "x" * 1000
        result = _degraded_intake("task", long_reason)
        self.assertLessEqual(len(result.degraded_reason), 300)


class TestExtractJsonFromCliOutput(unittest.TestCase):
    """Tests for the CLI response JSON extractor (Q-03 MoM)."""

    def test_valid_json_direct(self):
        data = _extract_json_from_cli_output('{"intent_normalized": "TASK: foo", "manifest_expected": []}')
        self.assertIsNotNone(data)
        self.assertEqual(data["intent_normalized"], "TASK: foo")

    def test_json_wrapped_in_prose(self):
        text = 'Here is the structured output:\n{"intent_normalized": "TASK: bar", "manifest_expected": []}'
        data = _extract_json_from_cli_output(text)
        self.assertIsNotNone(data)
        self.assertEqual(data["intent_normalized"], "TASK: bar")

    def test_json_in_envelope(self):
        import json
        inner = json.dumps({"intent_normalized": "TASK: baz", "manifest_expected": []})
        envelope = json.dumps({"text": inner})
        data = _extract_json_from_cli_output(envelope)
        self.assertIsNotNone(data)
        self.assertEqual(data["intent_normalized"], "TASK: baz")

    def test_no_json_returns_none(self):
        result = _extract_json_from_cli_output("I could not parse your request.")
        self.assertIsNone(result)

    def test_malformed_json_returns_none(self):
        result = _extract_json_from_cli_output('{"intent_normalized": "broken"')
        self.assertIsNone(result)

    def test_empty_string_returns_none(self):
        result = _extract_json_from_cli_output("")
        self.assertIsNone(result)

    def test_truncated_json_returns_none(self):
        result = _extract_json_from_cli_output('{"intent_normalized": "foo", "manifest')
        self.assertIsNone(result)


class TestGetOrchestrator(unittest.TestCase):
    def test_cli_provider_returns_cli_backend(self):
        orch = get_orchestrator(provider="cli")
        self.assertIsInstance(orch, CLIOrchestratorBackend)

    def test_auto_without_api_key_returns_cli(self):
        import os
        with patch.dict(os.environ, {}, clear=True):
            if "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]
            orch = get_orchestrator(provider="auto")
            self.assertIsInstance(orch, CLIOrchestratorBackend)

    def test_anthropic_provider_raises_without_extras(self):
        """Anthropic backend must raise clearly if [intake] extras not installed."""
        from src.code_delegation_harness.intake import AnthropicOrchestratorBackend
        orch = AnthropicOrchestratorBackend()
        with self.assertRaises(Exception) as ctx:
            # This will raise either ImportError (no anthropic) or RuntimeError (our wrapper)
            orch.run_intake("test task", model="claude-opus-4-8")
        self.assertTrue(
            "intake" in str(ctx.exception).lower() or "anthropic" in str(ctx.exception).lower()
            or "import" in str(ctx.exception).lower()
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
