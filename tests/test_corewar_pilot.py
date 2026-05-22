import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from pdrq.core.types import Program
from pdrq.corewar.mars import MarsConfig, MarsRunner, parse_koth_scores
from pdrq.corewar.redcode import dominant_opcode, extract_redcode, static_features
from pdrq.gemini.client import BudgetGuard, GeminiRedcodeGenerator, StubRedcodeGenerator, _strategy_summary

from experiments.run_corewar_scaleup_batch import completed_run_id, run_id_for


ROOT = Path(__file__).resolve().parents[1]


class CoreWarPilotTests(unittest.TestCase):
    def test_parse_koth_scores(self):
        self.assertEqual(parse_koth_scores("1 0\n9 0\n"), (1, 9))

    def test_redcode_helpers(self):
        source = extract_redcode("```redcode\nMOV 0, 1\n```")
        self.assertIn("MOV", source)
        self.assertEqual(dominant_opcode("start mov 0, 1\n"), "mov")
        self.assertGreater(static_features("DAT #0, #0\n")["dat_density"], 0.0)

    def test_budget_guard_blocks_projected_overrun(self):
        guard = BudgetGuard(max_calls=1, max_estimated_cost_usd=0.000001)
        with self.assertRaises(RuntimeError):
            guard.reserve("x" * 1000, 700)

    def test_stub_generator_returns_redcode(self):
        parent = Program("p", "MOV 0, 1\n")
        proposal = StubRedcodeGenerator(1).propose([parent], [parent], 1, "linear_drq")
        self.assertIn(";redcode-94", proposal.source)

    def test_gemini_generator_retries_transient_transport_error(self):
        class FakeModels:
            def __init__(self):
                self.calls = 0

            def generate_content(self, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise httpx.ReadTimeout("temporary read timeout")
                usage = type("Usage", (), {"prompt_token_count": 10, "candidates_token_count": 20})()
                return type("Response", (), {"text": ";redcode-94\nMOV 0, 1\n", "usage_metadata": usage})()

        generator = GeminiRedcodeGenerator.__new__(GeminiRedcodeGenerator)
        generator.project = "p"
        generator.location = "us-central1"
        generator.model = "gemini-2.5-flash"
        generator.budget = BudgetGuard(max_calls=2, max_estimated_cost_usd=1)
        generator.max_output_tokens = 700
        generator.temperature = 0.8
        generator.max_retries = 1
        generator.retry_initial_delay_seconds = 0
        generator.client = type("FakeClient", (), {"models": FakeModels()})()

        parent = Program("p", "MOV 0, 1\n")
        proposal = generator.propose([parent], [parent], 1, "linear_drq")

        self.assertEqual(generator.client.models.calls, 2)
        self.assertEqual(generator.budget.calls, 1)
        self.assertIn("MOV", proposal.source)

    def test_plain_redcode_strategy_summary(self):
        source = ";redcode-94\n;strategy simple imp\nMOV 0, 1\n"
        self.assertEqual(_strategy_summary(source), "strategy simple imp")

    def test_scaleup_run_id_helpers(self):
        self.assertEqual(run_id_for("batch", "long", 12, 3), "batch_long_s012_a03")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "batch_current_s001_a02"
            run.mkdir(parents=True, exist_ok=True)
            (run / "summary.json").write_text("{}\n", encoding="utf-8")
            self.assertEqual(completed_run_id(root, "batch", "current", 1), "batch_current_s001_a02")

    def test_pmars_validation_timeout_is_invalid(self):
        runner = MarsRunner(MarsConfig(binary=ROOT / "vendor" / "pmars-bin", timeout_seconds=0.1))
        expired = subprocess.TimeoutExpired(cmd=["pmars"], timeout=0.1)
        with patch("pdrq.corewar.mars.subprocess.run", side_effect=expired):
            valid, output = runner.validate(Program("timeout", "MOV 0, 1\n"))
        self.assertFalse(valid)
        self.assertIn("timed out", output)

    @unittest.skipUnless((ROOT / "vendor" / "pmars-bin").exists(), "pMARS binary not installed")
    def test_pmars_runs_pair(self):
        red = Program("imp", (ROOT / "data" / "corewar" / "seeds" / "imp.red").read_text())
        blue = Program("dwarf", (ROOT / "data" / "corewar" / "seeds" / "dwarf.red").read_text())
        runner = MarsRunner(MarsConfig(binary=ROOT / "vendor" / "pmars-bin", rounds=2, timeout_seconds=5.0))
        valid, output = runner.validate(red)
        self.assertTrue(valid, output)
        result = runner.run_pair(red, blue, 100)
        self.assertEqual(result.red_id, "imp")
        self.assertEqual(result.blue_id, "dwarf")

    @unittest.skipUnless((ROOT / "vendor" / "pmars-bin").exists(), "pMARS binary not installed")
    def test_pmars_rejects_comments_only_warning(self):
        runner = MarsRunner(MarsConfig(binary=ROOT / "vendor" / "pmars-bin", rounds=2, timeout_seconds=5.0))
        valid, output = runner.validate(Program("empty", ";redcode-94\n;name Empty\n"))
        self.assertFalse(valid, output)
        self.assertIn("No instructions", output)


if __name__ == "__main__":
    unittest.main()
