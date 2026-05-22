import unittest
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdrq.algorithms import PopulationConfig, run_linear_drq, run_population_drq, run_static_evolution
from pdrq.metrics import pairwise_diversity, role_entropy
from pdrq.toy_ecology import ROLE_NAMES, ToyCoreWarSurrogate


class ToyEcologyTests(unittest.TestCase):
    def test_duel_is_antisymmetric_for_role_centers(self):
        game = ToyCoreWarSurrogate(1)
        a = game.seed_warrior("bomber")
        b = game.seed_warrior("scanner")
        margin_ab = game.duel(a, b)
        margin_ba = game.duel(b, a)
        self.assertLess(abs(margin_ab + margin_ba), 0.12)

    def test_population_run_keeps_configured_size(self):
        config = PopulationConfig("test", population_size=12, generations=6, candidates_per_generation=4)
        trace = run_population_drq(config, seed=2)
        self.assertEqual(len(trace.population), 12)
        self.assertEqual(len(trace.records), 6)
        self.assertGreaterEqual(pairwise_diversity(trace.population), 0.0)

    def test_baselines_produce_records(self):
        static = run_static_evolution(seed=3, generations=5, candidates_per_generation=3)
        linear = run_linear_drq(seed=3, generations=5, candidates_per_generation=3)
        self.assertEqual(len(static.records), 5)
        self.assertEqual(len(linear.records), 5)
        self.assertEqual(len(static.population), 1)
        self.assertEqual(len(linear.population), 1)

    def test_entropy_bounds(self):
        game = ToyCoreWarSurrogate(4)
        population = [game.seed_warrior(role) for role in ROLE_NAMES]
        self.assertGreater(role_entropy(population), 2.0)
        self.assertLessEqual(role_entropy(population), np.log2(len(ROLE_NAMES)) + 1e-9)


if __name__ == "__main__":
    unittest.main()
