"""Tests for the confirmation loop (Phase 4)."""
import unittest
from unittest.mock import MagicMock, patch

from src.code_delegation_harness.intake import ArtifactExpectation, IntakeResult
from src.code_delegation_harness.trace import ConfirmationBlock


class TestConfirmationLoop(unittest.TestCase):
    """
    Tests for _run_confirmation_loop in harness.py.

    The confirmation loop is opt-in (--confirm). Default is silent passthrough.
    Key invariants:
      - shown_to_user=False when --confirm not passed
      - Max 2 correction rounds, run proceeds regardless after cap
      - Corrections captured in ConfirmationBlock for trace/tuning
    """

    def _make_intake_result(self, normalized="TASK: Add login", manifest=None):
        return IntakeResult(
            intent_detection="human",
            was_normalized=True,
            intent_normalized=normalized,
            manifest_expected=manifest or [
                ArtifactExpectation(type="file", name="auth.py", description="OAuth handler")
            ],
        )

    def test_silent_passthrough_default(self):
        """Without --confirm, confirmation block shows shown_to_user=False."""
        block = ConfirmationBlock()
        self.assertFalse(block.shown_to_user)
        self.assertEqual(block.iterations, 0)
        self.assertEqual(block.corrections, [])

    def test_confirm_yes_proceed(self):
        """User presses enter — no correction, single round, proceeds."""
        from src.code_delegation_harness.harness import _run_confirmation_loop
        intake = self._make_intake_result()
        with patch("builtins.input", return_value=""):
            block = _run_confirmation_loop(intake_result=intake, quiet=True)
        self.assertTrue(block.shown_to_user)
        self.assertEqual(block.iterations, 1)
        self.assertEqual(block.corrections, [])

    def test_confirm_correction_is_captured(self):
        """User provides correction text — captured in corrections list."""
        from src.code_delegation_harness.harness import _run_confirmation_loop
        intake = self._make_intake_result()
        # First input: correction. Second input: accept (enter).
        with patch("builtins.input", side_effect=["use JWT not OAuth", ""]):
            with patch("src.code_delegation_harness.harness.get_orchestrator") as mock_get_orch:
                with patch("src.code_delegation_harness.harness.run_intake_gate") as mock_rig:
                    mock_rig.return_value = IntakeResult(
                        was_normalized=True,
                        intent_normalized="TASK: Add JWT login",
                        manifest_expected=[ArtifactExpectation(type="file", name="jwt.py", description="JWT")],
                    )
                    mock_get_orch.return_value = MagicMock()
                    block = _run_confirmation_loop(intake_result=intake, quiet=True)
        self.assertTrue(block.shown_to_user)
        self.assertEqual(len(block.corrections), 1)
        self.assertEqual(block.corrections[0]["raw_correction"], "use JWT not OAuth")

    def test_two_round_cap_enforced(self):
        """After 2 correction rounds, run proceeds regardless."""
        from src.code_delegation_harness.harness import _run_confirmation_loop
        intake = self._make_intake_result()
        # Two non-empty inputs (both corrections) — should cap after round 2
        with patch("builtins.input", side_effect=["fix this", "and this"]):
            with patch("src.code_delegation_harness.harness.get_orchestrator") as mock_get_orch:
                with patch("src.code_delegation_harness.harness.run_intake_gate") as mock_rig:
                    mock_rig.return_value = IntakeResult(
                        was_normalized=True,
                        intent_normalized="updated",
                        manifest_expected=[],
                    )
                    mock_get_orch.return_value = MagicMock()
                    block = _run_confirmation_loop(intake_result=intake, quiet=True)
        # Should have run through both rounds and stopped at 2
        self.assertEqual(block.iterations, 2)
        self.assertEqual(len(block.corrections), 2)

    def test_eof_on_input_proceeds_gracefully(self):
        """EOFError on input (non-interactive) should proceed without crashing."""
        from src.code_delegation_harness.harness import _run_confirmation_loop
        intake = self._make_intake_result()
        with patch("builtins.input", side_effect=EOFError):
            block = _run_confirmation_loop(intake_result=intake, quiet=True)
        self.assertTrue(block.shown_to_user)
        self.assertEqual(block.corrections, [])

    def test_corrections_capture_updated_normalized(self):
        """Each correction entry contains the updated normalized prompt."""
        from src.code_delegation_harness.harness import _run_confirmation_loop
        intake = self._make_intake_result()
        with patch("builtins.input", side_effect=["use Redis not in-memory", ""]):
            with patch("src.code_delegation_harness.harness.get_orchestrator") as mock_get_orch:
                with patch("src.code_delegation_harness.harness.run_intake_gate") as mock_rig:
                    mock_rig.return_value = IntakeResult(
                        was_normalized=True,
                        intent_normalized="TASK: Add Redis cache",
                        manifest_expected=[],
                    )
                    mock_get_orch.return_value = MagicMock()
                    block = _run_confirmation_loop(intake_result=intake, quiet=True)
        self.assertIn("updated_normalized", block.corrections[0])
        self.assertEqual(block.corrections[0]["updated_normalized"], "TASK: Add Redis cache")


if __name__ == "__main__":
    unittest.main(verbosity=2)
