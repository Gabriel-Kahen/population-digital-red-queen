"""A small ecological game used for end-to-end artifact validation.

The surrogate intentionally has Core War-like strategic labels, but it is not a
Redcode interpreter. It provides deterministic, frequency-dependent matchups so
the Population DRQ machinery can be tested without LLM calls or external tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np


ROLE_NAMES = (
    "bomber",
    "scanner",
    "replicator",
    "anti_scanner",
    "defender",
    "hybrid",
)

ROLE_INDEX: Mapping[str, int] = {name: i for i, name in enumerate(ROLE_NAMES)}

ROLE_CENTROIDS = np.array(
    [
        [0.92, 0.20, 0.22, 0.35, 0.30],  # bomber
        [0.45, 0.92, 0.25, 0.35, 0.56],  # scanner
        [0.30, 0.28, 0.94, 0.42, 0.80],  # replicator
        [0.66, 0.30, 0.40, 0.92, 0.45],  # anti_scanner
        [0.22, 0.35, 0.50, 0.82, 0.92],  # defender
        [0.58, 0.60, 0.62, 0.60, 0.62],  # hybrid
    ],
    dtype=float,
)

# Positive values favor the row role against the column role.
ROLE_PAYOFFS = np.array(
    [
        [0.00, 0.35, -0.45, 0.12, 0.20, 0.05],
        [-0.35, 0.00, 0.38, -0.42, 0.18, 0.08],
        [0.45, -0.38, 0.00, 0.20, -0.34, 0.06],
        [-0.12, 0.42, -0.20, 0.00, -0.26, 0.08],
        [-0.20, -0.18, 0.34, 0.26, 0.00, 0.10],
        [-0.05, -0.08, -0.06, -0.08, -0.10, 0.00],
    ],
    dtype=float,
)

TRAIT_MATCHUP = np.array(
    [
        [0.12, -0.03, -0.08, 0.06, 0.02],
        [-0.02, 0.10, -0.02, -0.06, 0.05],
        [-0.08, -0.03, 0.12, 0.02, 0.06],
        [0.03, -0.09, 0.02, 0.11, -0.02],
        [0.02, 0.03, 0.05, -0.02, 0.10],
    ],
    dtype=float,
)


@dataclass(frozen=True)
class Warrior:
    """A synthetic warrior with a role, numeric behavior traits, and ancestry."""

    warrior_id: str
    role: str
    traits: np.ndarray
    source: str
    generation: int = 0
    parent_ids: tuple[str, ...] = field(default_factory=tuple)
    born_from: str = "seed"

    def descriptor(self) -> np.ndarray:
        role_vec = np.zeros(len(ROLE_NAMES), dtype=float)
        role_vec[ROLE_INDEX[self.role]] = 1.0
        return np.concatenate([role_vec, self.traits])


class ToyCoreWarSurrogate:
    """Deterministic strategic ecology with semantic mutation operators."""

    def __init__(self, seed: int = 0):
        self.rng = np.random.default_rng(seed)
        self._counter = 0

    def seed_warrior(self, role: str, generation: int = 0) -> Warrior:
        if role not in ROLE_INDEX:
            raise ValueError(f"unknown role: {role}")
        traits = np.clip(
            ROLE_CENTROIDS[ROLE_INDEX[role]]
            + self.rng.normal(0.0, 0.055, size=ROLE_CENTROIDS.shape[1]),
            0.0,
            1.0,
        )
        return self._make_warrior(role, traits, generation, (), "seed")

    def heldout_suite(self) -> list[Warrior]:
        """A fixed mixed-role suite used as synthetic held-out opponents."""

        state = self.rng.bit_generator.state
        self.rng = np.random.default_rng(10_003)
        suite = [self.seed_warrior(role, generation=-1) for role in ROLE_NAMES]
        suite.extend(self.seed_warrior(role, generation=-1) for role in ("bomber", "scanner", "defender"))
        self.rng.bit_generator.state = state
        return suite

    def mutate(
        self,
        parents: Sequence[Warrior],
        opponents: Sequence[Warrior],
        generation: int,
        mode: str = "semantic",
    ) -> Warrior:
        if not parents:
            raise ValueError("mutation requires at least one parent")
        parent = parents[int(self.rng.integers(0, len(parents)))]
        role = self._choose_role(parent, opponents, mode)
        target = ROLE_CENTROIDS[ROLE_INDEX[role]]
        pull = 0.32 if role != parent.role else 0.18
        traits = (1.0 - pull) * parent.traits + pull * target
        traits += self.rng.normal(0.0, 0.075, size=traits.shape)
        if len(parents) > 1 and self.rng.random() < 0.45:
            mate = parents[int(self.rng.integers(0, len(parents)))]
            traits = 0.72 * traits + 0.28 * mate.traits
        traits = np.clip(traits, 0.0, 1.0)
        return self._make_warrior(role, traits, generation, tuple(p.warrior_id for p in parents), mode)

    def duel(self, a: Warrior, b: Warrior) -> float:
        """Return row-player margin in [-1, 1]."""

        ri = ROLE_INDEX[a.role]
        rj = ROLE_INDEX[b.role]
        role_margin = ROLE_PAYOFFS[ri, rj]
        attack = float(a.traits.T @ TRAIT_MATCHUP @ ROLE_CENTROIDS[rj])
        counter_attack = float(b.traits.T @ TRAIT_MATCHUP @ ROLE_CENTROIDS[ri])
        trait_margin = attack - counter_attack
        specialization = 0.10 * (
            np.linalg.norm(b.traits - ROLE_CENTROIDS[rj])
            - np.linalg.norm(a.traits - ROLE_CENTROIDS[ri])
        )
        margin = role_margin + trait_margin + specialization
        return float(np.clip(margin, -1.0, 1.0))

    def score_against(self, warrior: Warrior, opponents: Iterable[Warrior]) -> float:
        scores = [self.duel(warrior, opponent) for opponent in opponents if opponent.warrior_id != warrior.warrior_id]
        return float(np.mean(scores)) if scores else 0.0

    def _choose_role(self, parent: Warrior, opponents: Sequence[Warrior], mode: str) -> str:
        if mode == "random" or not opponents:
            return ROLE_NAMES[int(self.rng.integers(0, len(ROLE_NAMES)))]

        opponent_counts = np.zeros(len(ROLE_NAMES), dtype=float)
        for opponent in opponents:
            opponent_counts[ROLE_INDEX[opponent.role]] += 1.0
        opponent_counts /= max(1.0, opponent_counts.sum())

        counter_value = ROLE_PAYOFFS @ opponent_counts
        parent_bias = np.zeros(len(ROLE_NAMES), dtype=float)
        parent_bias[ROLE_INDEX[parent.role]] = 0.35
        logits = 3.8 * counter_value + parent_bias
        logits -= logits.max()
        probs = np.exp(logits)
        probs /= probs.sum()
        return ROLE_NAMES[int(self.rng.choice(len(ROLE_NAMES), p=probs))]

    def _make_warrior(
        self,
        role: str,
        traits: np.ndarray,
        generation: int,
        parents: tuple[str, ...],
        born_from: str,
    ) -> Warrior:
        self._counter += 1
        trait_text = ", ".join(f"{v:.3f}" for v in traits)
        source = (
            f"; synthetic surrogate warrior\n"
            f"; role: {role}\n"
            f"; traits: [{trait_text}]\n"
            f"; born_from: {born_from}\n"
        )
        return Warrior(
            warrior_id=f"w{self._counter:05d}",
            role=role,
            traits=traits,
            source=source,
            generation=generation,
            parent_ids=parents,
            born_from=born_from,
        )
