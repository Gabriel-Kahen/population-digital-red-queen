#!/usr/bin/env python3
"""Run the real Core War PDRQ pilot harness.

Defaults are intentionally no-spend: the stub generator exercises the evaluator,
storage, scoring, and replacement paths without calling Gemini.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdrq.core.store import ArtifactStore
from pdrq.core.types import CandidateProposal, Program
from pdrq.corewar.corpus import load_programs
from pdrq.corewar.mars import MarsConfig, MarsError, MarsRunner
from pdrq.corewar.redcode import dominant_opcode, normalize_source, source_hash, static_features
from pdrq.gemini.client import BudgetGuard, GeminiRedcodeGenerator, StubRedcodeGenerator


CONDITIONS = ("linear_drq", "pop_current", "pop_archive_niche")


def main() -> None:
    args = parse_args()
    if args.generator == "gemini" and not args.allow_paid_api:
        raise SystemExit("Refusing paid API calls. Re-run with --allow-paid-api after the dry run passes.")

    project = args.project or gcloud_project()
    if args.generator == "gemini" and not project:
        raise SystemExit("Gemini generator requires --project or an active gcloud project.")

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    store = ArtifactStore(args.output_dir / run_id)
    rng = random.Random(args.seed)
    mars = MarsRunner(
        MarsConfig(
            binary=args.mars_bin,
            rounds=args.match_rounds,
            timeout_seconds=args.match_timeout,
        )
    )
    seeds = load_programs(args.seed_dir)
    heldout = load_programs(args.heldout_dir, generation=-1, role="heldout")
    if len(seeds) < 2 or len(heldout) < 1:
        raise SystemExit("Need at least two seed warriors and one held-out warrior.")

    config = vars(args) | {"project": project, "run_id": run_id, "conditions": args.conditions}
    store.write_config(config)
    validate_corpus(mars, [*seeds, *heldout], store)

    budget = BudgetGuard(max_calls=args.max_llm_calls, max_estimated_cost_usd=args.max_estimated_cost_usd)
    generator = make_generator(args, project, budget)
    summaries = []
    for condition in args.conditions:
        summary = run_condition(condition, args, seeds, heldout, mars, generator, store, rng)
        summaries.append(summary)
        store.append_event("condition_summary", summary)

    final = {"run_id": run_id, "generator": args.generator, "budget": budget.state(), "conditions": summaries}
    store.write_summary(final)
    print(json.dumps(final, default=lambda value: getattr(value, "__dict__", str(value)), indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=["linear_drq"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--generations", type=int, default=1)
    parser.add_argument("--candidates", type=int, default=2)
    parser.add_argument("--population-size", type=int, default=6)
    parser.add_argument("--opponent-sample", type=int, default=3)
    parser.add_argument("--archive-weight", type=float, default=0.35)
    parser.add_argument("--offsets", type=int, nargs="+", default=[100, 500])
    parser.add_argument("--match-rounds", type=int, default=10)
    parser.add_argument("--match-timeout", type=float, default=10.0)
    parser.add_argument("--mars-bin", type=Path, default=ROOT / "vendor" / "pmars-bin")
    parser.add_argument("--seed-dir", type=Path, default=ROOT / "data" / "corewar" / "seeds")
    parser.add_argument("--heldout-dir", type=Path, default=ROOT / "data" / "corewar" / "heldout")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "corewar_pilot")
    parser.add_argument("--run-id")
    parser.add_argument("--generator", choices=("stub", "gemini"), default="stub")
    parser.add_argument("--allow-paid-api", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--max-output-tokens", type=int, default=700)
    parser.add_argument("--max-llm-calls", type=int, default=20)
    parser.add_argument("--max-estimated-cost-usd", type=float, default=1.0)
    parser.add_argument("--stop-invalid-rate", type=float, default=0.70)
    parser.add_argument("--min-candidate-instructions", type=int, default=3)
    return parser.parse_args()


def make_generator(args: argparse.Namespace, project: str | None, budget: BudgetGuard):
    if args.generator == "stub":
        return StubRedcodeGenerator(args.seed)
    assert project is not None
    return GeminiRedcodeGenerator(
        project=project,
        location=args.location,
        model=args.model,
        budget=budget,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
    )


def run_condition(
    condition: str,
    args: argparse.Namespace,
    seeds: Sequence[Program],
    heldout: Sequence[Program],
    mars: MarsRunner,
    generator,
    store: ArtifactStore,
    rng: random.Random,
) -> dict[str, object]:
    population = list(seeds[: args.population_size])
    while len(population) < args.population_size:
        population.append(seeds[len(population) % len(seeds)])
    archive = list(dict((program.program_id, program) for program in population).values())
    champion = population[0]
    accepted = 0
    invalid = 0
    generated = 0
    feedback = ""

    for generation in range(1, args.generations + 1):
        for _ in range(args.candidates):
            generated += 1
            parents, opponents = context_for(condition, champion, population, archive, args, rng)
            proposal = generator.propose(parents, opponents, generation, condition, feedback=feedback)
            candidate = proposal_to_program(proposal, generation, parents, condition, generated)
            store.save_proposal(candidate.program_id, proposal)
            valid, validation_output = mars.validate(candidate)
            features = static_features(candidate.source)
            if valid and features["instruction_count"] < args.min_candidate_instructions:
                valid = False
                message = (
                    f"Candidate has fewer than {args.min_candidate_instructions} instructions: "
                    f"{features['instruction_count']:.0f}"
                )
                validation_output = f"{validation_output}\n{message}".strip()
            store.append_event(
                "candidate",
                {
                    "condition": condition,
                    "generation": generation,
                    "candidate_id": candidate.program_id,
                    "valid": valid,
                    "validation_output": validation_output,
                    "parents": [parent.program_id for parent in parents],
                    "opponents": [opponent.program_id for opponent in opponents],
                    "strategy_summary": proposal.strategy_summary,
                    "features": features,
                },
            )
            if not valid:
                invalid += 1
                feedback = f"Previous candidate was invalid: {validation_output}"
                if generated >= 10 and invalid / generated > args.stop_invalid_rate:
                    raise RuntimeError(f"invalid Redcode rate exceeded threshold: {invalid}/{generated}")
                continue
            feedback = ""
            store.save_program(candidate)
            if condition == "linear_drq":
                score = score_against(mars, candidate, archive, args.offsets, store)
                champion_score = score_against(mars, champion, archive, args.offsets, store)
                if score >= champion_score:
                    champion = candidate
                    archive.append(candidate)
                    accepted += 1
            else:
                score = score_against(mars, candidate, opponents, args.offsets, store)
                index = replacement_index(condition, mars, population, opponents, args.offsets, store, candidate)
                incumbent_score = score_against(mars, population[index], opponents, args.offsets, store)
                if score > incumbent_score:
                    population[index] = candidate
                    archive.append(candidate)
                    champion = max(population, key=lambda program: score_against(mars, program, heldout, args.offsets, store))
                    accepted += 1
        store.append_event(
            "generation",
            {
                "condition": condition,
                "generation": generation,
                "champion": champion.program_id,
                "population": [program.program_id for program in population],
                "archive_size": len(archive),
            },
        )

    final_population = [champion] if condition == "linear_drq" else population
    heldout_scores = {
        program.program_id: score_against(mars, program, heldout, args.offsets, store)
        for program in final_population
    }
    return {
        "condition": condition,
        "generated": generated,
        "valid": generated - invalid,
        "accepted": accepted,
        "invalid": invalid,
        "champion": champion.program_id,
        "best_heldout": max(heldout_scores.values()),
        "mean_heldout": mean(heldout_scores.values()),
        "population": [program.program_id for program in final_population],
    }


def context_for(
    condition: str,
    champion: Program,
    population: Sequence[Program],
    archive: Sequence[Program],
    args: argparse.Namespace,
    rng: random.Random,
) -> tuple[list[Program], list[Program]]:
    if condition == "linear_drq":
        archive_sample = rng.sample(list(archive), k=min(args.opponent_sample, len(archive)))
        if champion.program_id not in {program.program_id for program in archive_sample}:
            archive_sample.append(champion)
        return [champion], archive_sample
    parents = [rng.choice(list(population))]
    live_n = max(1, args.opponent_sample)
    opponents = rng.sample(list(population), k=min(live_n, len(population)))
    if condition == "pop_archive_niche" and archive:
        archive_n = max(1, round(args.archive_weight * args.opponent_sample))
        opponents.extend(rng.sample(list(archive), k=min(archive_n, len(archive))))
    return parents, opponents


def replacement_index(
    condition: str,
    mars: MarsRunner,
    population: Sequence[Program],
    opponents: Sequence[Program],
    offsets: Sequence[int],
    store: ArtifactStore,
    candidate: Program,
) -> int:
    scores = [score_against(mars, program, opponents, offsets, store) for program in population]
    if condition != "pop_archive_niche":
        return min(range(len(population)), key=lambda index: scores[index])
    niche = dominant_opcode(candidate.source)
    same_niche = [i for i, program in enumerate(population) if dominant_opcode(program.source) == niche]
    if same_niche:
        return min(same_niche, key=lambda index: scores[index])
    return min(range(len(population)), key=lambda index: scores[index])


def score_against(
    mars: MarsRunner,
    program: Program,
    opponents: Iterable[Program],
    offsets: Sequence[int],
    store: ArtifactStore,
) -> float:
    margins: list[float] = []
    for opponent in opponents:
        if opponent.program_id == program.program_id:
            continue
        try:
            results = mars.evaluate(program, opponent, offsets)
        except MarsError as exc:
            margins.append(-1.0)
            store.append_event(
                "match_error",
                {
                    "red_id": program.program_id,
                    "blue_id": opponent.program_id,
                    "error": str(exc),
                },
            )
            continue
        for result in results:
            margins.append(result.margin)
            store.append_match(result.__dict__)
    return mean(margins) if margins else 0.0


def proposal_to_program(
    proposal: CandidateProposal,
    generation: int,
    parents: Sequence[Program],
    condition: str,
    ordinal: int,
) -> Program:
    source = normalize_source(proposal.source)
    digest = source_hash(source)
    return Program(
        program_id=f"{condition}_g{generation:03d}_c{ordinal:04d}_{digest[:8]}",
        source=source,
        generation=generation,
        parent_ids=tuple(parent.program_id for parent in parents),
        metadata={"condition": condition, "sha256": digest, "model": proposal.model},
    )


def validate_corpus(mars: MarsRunner, programs: Sequence[Program], store: ArtifactStore) -> None:
    for program in programs:
        valid, output = mars.validate(program)
        store.save_program(program)
        store.append_event(
            "corpus_program",
            {
                "program_id": program.program_id,
                "valid": valid,
                "validation_output": output,
                "metadata": dict(program.metadata),
                "features": static_features(program.source),
            },
        )
        if not valid:
            raise RuntimeError(f"invalid corpus warrior {program.program_id}: {output}")


def gcloud_project() -> str | None:
    try:
        completed = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    project = completed.stdout.strip()
    if not project or project == "(unset)":
        return None
    return project


if __name__ == "__main__":
    main()
