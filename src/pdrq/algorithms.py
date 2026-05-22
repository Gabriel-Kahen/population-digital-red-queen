"""Population Digital Red Queen algorithm variants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .metrics import novelty, pairwise_diversity, portfolio_score, role_entropy
from .toy_ecology import ROLE_NAMES, ToyCoreWarSurrogate, Warrior


@dataclass
class PopulationConfig:
    name: str
    population_size: int = 24
    generations: int = 80
    candidates_per_generation: int = 12
    opponent_sample: int = 10
    archive_size: int = 0
    archive_weight: float = 0.0
    novelty_weight: float = 0.0
    persistence_weight: float = 0.0
    niche_protection: bool = False
    ecological_persistence: bool = False
    mutation_mode: str = "semantic"


@dataclass
class GenerationRecord:
    generation: int
    best_score: float
    best_heldout: float
    portfolio_heldout: float
    diversity: float
    entropy: float
    accepted_id: str | None
    role_counts: dict[str, int]
    population_ids: list[str]


@dataclass
class EvolutionTrace:
    name: str
    population: list[Warrior]
    archive: list[Warrior]
    records: list[GenerationRecord]
    all_warriors: dict[str, Warrior] = field(default_factory=dict)


def run_static_evolution(seed: int = 0, generations: int = 80, candidates_per_generation: int = 12) -> EvolutionTrace:
    """Static single-opponent LLM evolution baseline."""

    game = ToyCoreWarSurrogate(seed)
    fixed_opponents = [game.seed_warrior("bomber"), game.seed_warrior("scanner"), game.seed_warrior("defender")]
    champion = game.seed_warrior("hybrid")
    heldout = game.heldout_suite()
    all_warriors = {w.warrior_id: w for w in [champion, *fixed_opponents, *heldout]}
    records: list[GenerationRecord] = []
    archive = [champion]

    for generation in range(1, generations + 1):
        candidates = [
            game.mutate([champion], fixed_opponents, generation, mode="semantic")
            for _ in range(candidates_per_generation)
        ]
        for candidate in candidates:
            all_warriors[candidate.warrior_id] = candidate
        champion = max(candidates + [champion], key=lambda w: game.score_against(w, fixed_opponents))
        archive.append(champion)
        records.append(_record("static", generation, game, [champion], archive, heldout, champion.warrior_id))
    return EvolutionTrace("static", [champion], archive, records, all_warriors)


def run_linear_drq(seed: int = 0, generations: int = 80, candidates_per_generation: int = 12) -> EvolutionTrace:
    """Linear DRQ baseline: each new champion is selected against all previous champions."""

    game = ToyCoreWarSurrogate(seed)
    champion = game.seed_warrior("hybrid")
    archive = [champion]
    heldout = game.heldout_suite()
    all_warriors = {w.warrior_id: w for w in [champion, *heldout]}
    records: list[GenerationRecord] = []

    for generation in range(1, generations + 1):
        candidates = [
            game.mutate([champion], archive, generation, mode="semantic")
            for _ in range(candidates_per_generation)
        ]
        for candidate in candidates:
            all_warriors[candidate.warrior_id] = candidate
        champion = max(candidates, key=lambda w: game.score_against(w, archive))
        archive.append(champion)
        records.append(_record("linear", generation, game, [champion], archive, heldout, champion.warrior_id))
    return EvolutionTrace("linear_drq", [champion], archive, records, all_warriors)


def run_population_drq(config: PopulationConfig, seed: int = 0) -> EvolutionTrace:
    """Run a population-level Red Queen variant."""

    game = ToyCoreWarSurrogate(seed)
    rng = np.random.default_rng(seed + 1_377)
    population = _initial_population(game, config.population_size)
    archive = list(population)
    heldout = game.heldout_suite()
    all_warriors = {w.warrior_id: w for w in [*population, *heldout]}
    records: list[GenerationRecord] = []

    for generation in range(1, config.generations + 1):
        accepted_id = None
        for _ in range(config.candidates_per_generation):
            opponents = _sample_opponents(population, archive, config, rng)
            parents = _select_parents(game, population, opponents, rng)
            candidate = game.mutate(parents, opponents, generation, mode=config.mutation_mode)
            all_warriors[candidate.warrior_id] = candidate
            candidate_score = _candidate_score(game, candidate, opponents, population, archive, config, generation)
            replacement_index = _replacement_index(game, population, opponents, archive, config, generation)
            replacement = population[replacement_index]
            replacement_score = _candidate_score(game, replacement, opponents, population, archive, config, generation)
            if candidate_score > replacement_score:
                population[replacement_index] = candidate
                archive.append(candidate)
                accepted_id = candidate.warrior_id
        archive = _trim_archive(archive, config.archive_size)
        records.append(_record(config.name, generation, game, population, archive, heldout, accepted_id))

    return EvolutionTrace(config.name, population, archive, records, all_warriors)


def _initial_population(game: ToyCoreWarSurrogate, size: int) -> list[Warrior]:
    population = []
    for i in range(size):
        population.append(game.seed_warrior(ROLE_NAMES[i % len(ROLE_NAMES)]))
    return population


def _sample_opponents(
    population: Sequence[Warrior],
    archive: Sequence[Warrior],
    config: PopulationConfig,
    rng: np.random.Generator,
) -> list[Warrior]:
    live_n = max(1, int(round(config.opponent_sample * (1.0 - config.archive_weight))))
    archive_n = max(0, config.opponent_sample - live_n)
    opponents = _choice(population, live_n, rng)
    if archive and archive_n:
        opponents.extend(_choice(archive, archive_n, rng))
    return opponents


def _select_parents(
    game: ToyCoreWarSurrogate,
    population: Sequence[Warrior],
    opponents: Sequence[Warrior],
    rng: np.random.Generator,
) -> list[Warrior]:
    scored = [(game.score_against(w, opponents), w) for w in population]
    scored.sort(key=lambda item: item[0], reverse=True)
    top = [w for _, w in scored[: max(2, min(6, len(scored)))]]
    parents = [top[int(rng.integers(0, len(top)))]]
    if len(top) > 1 and rng.random() < 0.35:
        parents.append(top[int(rng.integers(0, len(top)))])
    return parents


def _candidate_score(
    game: ToyCoreWarSurrogate,
    candidate: Warrior,
    opponents: Sequence[Warrior],
    population: Sequence[Warrior],
    archive: Sequence[Warrior],
    config: PopulationConfig,
    generation: int,
) -> float:
    performance = game.score_against(candidate, opponents)
    novelty_term = config.novelty_weight * novelty(candidate, list(population) + list(archive))
    persistence_term = 0.0
    if config.ecological_persistence:
        age = max(0, generation - candidate.generation)
        persistence_term = config.persistence_weight * min(1.0, age / max(1, config.generations // 4))
    return performance + novelty_term + persistence_term


def _replacement_index(
    game: ToyCoreWarSurrogate,
    population: Sequence[Warrior],
    opponents: Sequence[Warrior],
    archive: Sequence[Warrior],
    config: PopulationConfig,
    generation: int,
) -> int:
    scores = [
        _candidate_score(game, warrior, opponents, population, archive, config, generation)
        for warrior in population
    ]
    if not config.niche_protection:
        return int(np.argmin(scores))

    role_counts = {role: sum(1 for w in population if w.role == role) for role in ROLE_NAMES}
    removable = [
        i
        for i, warrior in enumerate(population)
        if role_counts[warrior.role] > 1
    ]
    if not removable:
        return int(np.argmin(scores))

    redundancy = []
    for i in removable:
        warrior = population[i]
        same_role = [w for j, w in enumerate(population) if j != i and w.role == warrior.role]
        if same_role:
            nearest = min(float(np.linalg.norm(warrior.descriptor() - other.descriptor())) for other in same_role)
        else:
            nearest = 10.0
        redundancy.append((scores[i] - 0.08 * nearest, i))
    redundancy.sort(key=lambda item: item[0])
    return redundancy[0][1]


def _trim_archive(archive: list[Warrior], archive_size: int) -> list[Warrior]:
    if archive_size == 0:
        return []
    if archive_size < 0 or len(archive) <= archive_size:
        return archive
    return archive[-archive_size:]


def _choice(items: Sequence[Warrior], n: int, rng: np.random.Generator) -> list[Warrior]:
    if not items:
        return []
    idxs = rng.choice(len(items), size=min(n, len(items)), replace=len(items) < n)
    return [items[int(i)] for i in np.atleast_1d(idxs)]


def _record(
    name: str,
    generation: int,
    game: ToyCoreWarSurrogate,
    population: Sequence[Warrior],
    archive: Sequence[Warrior],
    heldout: Sequence[Warrior],
    accepted_id: str | None,
) -> GenerationRecord:
    best = max(population, key=lambda w: game.score_against(w, heldout))
    role_counts = {role: sum(1 for w in population if w.role == role) for role in ROLE_NAMES}
    return GenerationRecord(
        generation=generation,
        best_score=game.score_against(best, population),
        best_heldout=game.score_against(best, heldout),
        portfolio_heldout=portfolio_score(game, population, heldout),
        diversity=pairwise_diversity(population),
        entropy=role_entropy(population),
        accepted_id=accepted_id,
        role_counts=role_counts,
        population_ids=[w.warrior_id for w in population],
    )
