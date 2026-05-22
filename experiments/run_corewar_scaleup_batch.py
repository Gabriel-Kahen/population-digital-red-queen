#!/usr/bin/env python3
"""Run planned Core War scale-up batches with unique retry run IDs."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


PROFILES = {
    "current": {
        "generations": 6,
        "candidates": 40,
        "max_llm_calls": 720,
        "max_estimated_cost_usd": 2.0,
    },
    "long": {
        "generations": 12,
        "candidates": 40,
        "max_llm_calls": 1440,
        "max_estimated_cost_usd": 3.5,
    },
}


def main() -> None:
    args = parse_args()
    if args.generator == "gemini" and not args.allow_paid_api:
        raise SystemExit("Refusing paid API calls. Pass --allow-paid-api to run Gemini batches.")
    if args.parallel < 1:
        raise SystemExit("--parallel must be at least 1")

    batch_id = args.batch_id or datetime.now(timezone.utc).strftime("scaleup_%Y%m%dT%H%M%SZ")
    seeds = list(range(args.seed_start, args.seed_start + args.replicates))
    print(
        f"batch_id={batch_id} profile={args.profile} seeds={seeds[0]}..{seeds[-1]} "
        f"parallel={args.parallel} generator={args.generator}",
        flush=True,
    )
    if args.dry_run:
        for seed in seeds:
            print(" ".join(command_for_attempt(args, batch_id, seed, 1)))
        return

    failures: list[tuple[int, str]] = []
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        futures = {executor.submit(run_seed, args, batch_id, seed): seed for seed in seeds}
        for future in as_completed(futures):
            seed = futures[future]
            try:
                run_id = future.result()
            except Exception as exc:  # noqa: BLE001 - surface worker failure with seed context.
                failures.append((seed, str(exc)))
                print(f"FAILED seed={seed}: {exc}", flush=True)
            else:
                print(f"COMPLETE seed={seed} run_id={run_id}", flush=True)

    if failures:
        for seed, message in failures:
            print(f"seed {seed} failed: {message}", file=sys.stderr)
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--batch-id")
    parser.add_argument("--replicates", type=int, required=True)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--attempts", type=int, default=5)
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--retry-delay-seconds", type=float, default=60.0)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "corewar_pilot")
    parser.add_argument("--python", default=str(ROOT / ".venv" / "bin" / "python"))
    parser.add_argument("--generator", choices=("stub", "gemini"), default="gemini")
    parser.add_argument("--allow-paid-api", action="store_true")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--project")
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--conditions", nargs="+", default=["linear_drq", "pop_current", "pop_archive_niche"])
    parser.add_argument("--population-size", type=int, default=6)
    parser.add_argument("--opponent-sample", type=int, default=4)
    parser.add_argument("--archive-weight", type=float, default=0.35)
    parser.add_argument("--offsets", nargs="+", type=int, default=[100, 500, 1500])
    parser.add_argument("--match-rounds", type=int, default=20)
    parser.add_argument("--stop-invalid-rate", type=float, default=0.25)
    parser.add_argument("--min-candidate-instructions", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def run_seed(args: argparse.Namespace, batch_id: str, seed: int) -> str:
    completed = completed_run_id(args.output_dir, batch_id, args.profile, seed)
    if completed:
        print(f"SKIP seed={seed} existing={completed}", flush=True)
        return completed

    last_returncode = 0
    for attempt in range(1, args.attempts + 1):
        run_id = run_id_for(batch_id, args.profile, seed, attempt)
        run_dir = args.output_dir / run_id
        if (run_dir / "summary.json").exists():
            return run_id
        if run_dir.exists():
            print(f"SKIP_PARTIAL seed={seed} attempt={attempt} run_id={run_id}", flush=True)
            continue
        command = command_for_attempt(args, batch_id, seed, attempt)
        print(f"START seed={seed} attempt={attempt} run_id={run_id}", flush=True)
        completed_process = subprocess.run(command, cwd=ROOT, text=True)
        last_returncode = completed_process.returncode
        if last_returncode == 0 and (args.output_dir / run_id / "summary.json").exists():
            return run_id
        print(f"RETRY seed={seed} attempt={attempt} returncode={last_returncode}", flush=True)
        time.sleep(args.retry_delay_seconds)

    raise RuntimeError(f"exhausted {args.attempts} attempts; last return code {last_returncode}")


def completed_run_id(output_dir: Path, batch_id: str, profile: str, seed: int) -> str | None:
    prefix = f"{batch_id}_{profile}_s{seed:03d}_a"
    for summary in sorted(output_dir.glob(f"{prefix}*/summary.json")):
        return summary.parent.name
    return None


def run_id_for(batch_id: str, profile: str, seed: int, attempt: int) -> str:
    return f"{batch_id}_{profile}_s{seed:03d}_a{attempt:02d}"


def command_for_attempt(args: argparse.Namespace, batch_id: str, seed: int, attempt: int) -> list[str]:
    profile = PROFILES[args.profile]
    command = [
        args.python,
        "experiments/run_corewar_pilot.py",
        "--conditions",
        *args.conditions,
        "--generations",
        str(profile["generations"]),
        "--candidates",
        str(profile["candidates"]),
        "--population-size",
        str(args.population_size),
        "--opponent-sample",
        str(args.opponent_sample),
        "--archive-weight",
        str(args.archive_weight),
        "--offsets",
        *(str(offset) for offset in args.offsets),
        "--match-rounds",
        str(args.match_rounds),
        "--generator",
        args.generator,
        "--model",
        args.model,
        "--max-llm-calls",
        str(profile["max_llm_calls"]),
        "--max-estimated-cost-usd",
        str(profile["max_estimated_cost_usd"]),
        "--stop-invalid-rate",
        str(args.stop_invalid_rate),
        "--min-candidate-instructions",
        str(args.min_candidate_instructions),
        "--seed",
        str(seed),
        "--run-id",
        run_id_for(batch_id, args.profile, seed, attempt),
    ]
    if args.generator == "gemini":
        command.append("--allow-paid-api")
    if args.project:
        command.extend(["--project", args.project])
    if args.location:
        command.extend(["--location", args.location])
    return command


if __name__ == "__main__":
    main()
