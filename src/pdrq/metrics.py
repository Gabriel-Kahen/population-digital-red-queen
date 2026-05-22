"""Metrics for population-level Red Queen experiments."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence

import numpy as np

from .toy_ecology import ROLE_NAMES, ToyCoreWarSurrogate, Warrior


def pairwise_diversity(population: Sequence[Warrior]) -> float:
    if len(population) < 2:
        return 0.0
    descriptors = np.array([w.descriptor() for w in population], dtype=float)
    dists = []
    for i in range(len(descriptors)):
        for j in range(i + 1, len(descriptors)):
            dists.append(float(np.linalg.norm(descriptors[i] - descriptors[j])))
    return float(np.mean(dists))


def role_entropy(population: Sequence[Warrior]) -> float:
    if not population:
        return 0.0
    counts = Counter(w.role for w in population)
    probs = np.array([counts.get(role, 0) / len(population) for role in ROLE_NAMES], dtype=float)
    probs = probs[probs > 0]
    return float(-(probs * np.log2(probs)).sum())


def generality_score(game: ToyCoreWarSurrogate, warrior: Warrior, heldout: Iterable[Warrior]) -> float:
    return game.score_against(warrior, heldout)


def portfolio_score(game: ToyCoreWarSurrogate, population: Sequence[Warrior], heldout: Sequence[Warrior]) -> float:
    if not population or not heldout:
        return 0.0
    best_per_opponent = []
    for opponent in heldout:
        best_per_opponent.append(max(game.duel(warrior, opponent) for warrior in population))
    return float(np.mean(best_per_opponent))


def worst_case_score(game: ToyCoreWarSurrogate, population: Sequence[Warrior], heldout: Sequence[Warrior]) -> float:
    if not population or not heldout:
        return 0.0
    best_per_opponent = []
    for opponent in heldout:
        best_per_opponent.append(max(game.duel(warrior, opponent) for warrior in population))
    return float(np.min(best_per_opponent))


def novelty(candidate: Warrior, reference: Sequence[Warrior], k: int = 5) -> float:
    if not reference:
        return 0.0
    descriptor = candidate.descriptor()
    distances = sorted(float(np.linalg.norm(descriptor - other.descriptor())) for other in reference)
    return float(np.mean(distances[: min(k, len(distances))]))
