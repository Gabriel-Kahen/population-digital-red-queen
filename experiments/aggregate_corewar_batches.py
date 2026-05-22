#!/usr/bin/env python3
"""Aggregate completed Core War batch summaries."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import mean, stdev


ROOT = Path(__file__).resolve().parents[1]
RUN_RE = re.compile(r"^(?P<batch>.+)_(?P<profile>current|long)_s(?P<seed>\d+)_a(?P<attempt>\d+)$")
CONDITIONS = ("linear_drq", "pop_current", "pop_archive_niche")


def main() -> None:
    args = parse_args()
    runs = load_runs(args)
    if not runs:
        raise SystemExit("no completed summaries matched")

    print(f"completed_runs={len(runs)}")
    print(f"estimated_completed_cost_usd={sum(run['cost'] for run in runs):.3f}")
    print()
    for profile in sorted({run["profile"] for run in runs}):
        profile_runs = [run for run in runs if run["profile"] == profile]
        print_profile(profile, profile_runs)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "corewar_pilot")
    parser.add_argument("--profiles", nargs="+", default=["current", "long"])
    return parser.parse_args()


def load_runs(args: argparse.Namespace) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    for summary_path in sorted(args.output_dir.glob(f"{args.batch_id}_*/summary.json")):
        match = RUN_RE.match(summary_path.parent.name)
        if not match or match.group("profile") not in args.profiles:
            continue
        data = json.loads(summary_path.read_text())
        row: dict[str, object] = {
            "run_id": summary_path.parent.name,
            "profile": match.group("profile"),
            "seed": int(match.group("seed")),
            "attempt": int(match.group("attempt")),
            "cost": float(data["budget"]["estimated_cost_usd"]),
        }
        for condition in data["conditions"]:
            name = condition["condition"]
            row[f"{name}_mean"] = float(condition["mean_heldout"])
            row[f"{name}_best"] = float(condition["best_heldout"])
            row[f"{name}_accepted"] = float(condition["accepted"])
            row[f"{name}_invalid"] = float(condition["invalid"])
        runs.append(row)
    return runs


def print_profile(profile: str, runs: list[dict[str, object]]) -> None:
    print(f"## {profile}")
    print(f"n={len(runs)} cost_usd={sum(float(run['cost']) for run in runs):.3f}")
    for run in runs:
        winner = max(CONDITIONS, key=lambda condition: float(run[f"{condition}_mean"]))
        print(
            f"seed={run['seed']} attempt={run['attempt']} winner_mean={winner} "
            f"current={float(run['pop_current_mean']):.3f} "
            f"archive={float(run['pop_archive_niche_mean']):.3f} "
            f"linear={float(run['linear_drq_mean']):.3f}"
        )
    print()
    print_metric_block(runs, "mean")
    print_metric_block(runs, "best")
    print_paired_diffs(runs)
    print(f"winner_counts_mean={dict(Counter(max(CONDITIONS, key=lambda c: float(run[f'{c}_mean'])) for run in runs))}")
    print(f"winner_counts_best={dict(Counter(max(CONDITIONS, key=lambda c: float(run[f'{c}_best'])) for run in runs))}")
    print()


def print_metric_block(runs: list[dict[str, object]], metric: str) -> None:
    print(metric)
    for condition in CONDITIONS:
        values = [float(run[f"{condition}_{metric}"]) for run in runs]
        stats = summarize(values)
        print(
            f"  {condition}: mean={stats['mean']:.4f} sd={stats['sd']:.4f} "
            f"sem={stats['sem']:.4f} 95ci=+/-{stats['ci95']:.4f}"
        )


def print_paired_diffs(runs: list[dict[str, object]]) -> None:
    print("paired_mean_diffs")
    for label, left, right in [
        ("archive-current", "pop_archive_niche", "pop_current"),
        ("archive-linear", "pop_archive_niche", "linear_drq"),
        ("current-linear", "pop_current", "linear_drq"),
    ]:
        diffs = [float(run[f"{left}_mean"]) - float(run[f"{right}_mean"]) for run in runs]
        stats = summarize(diffs)
        wins = sum(diff > 0 for diff in diffs)
        losses = sum(diff < 0 for diff in diffs)
        ties = len(diffs) - wins - losses
        print(
            f"  {label}: mean={stats['mean']:.4f} sd={stats['sd']:.4f} "
            f"95ci=+/-{stats['ci95']:.4f} w/l/t={wins}/{losses}/{ties}"
        )


def summarize(values: list[float]) -> dict[str, float]:
    if len(values) == 1:
        return {"mean": values[0], "sd": 0.0, "sem": 0.0, "ci95": 0.0}
    sd = stdev(values)
    sem = sd / math.sqrt(len(values))
    # t critical values for common small n. Falls back to normal-ish 1.96 for larger n.
    t_crit = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365, 9: 2.306, 10: 2.262}
    ci95 = sem * t_crit.get(len(values), 1.96)
    return {"mean": mean(values), "sd": sd, "sem": sem, "ci95": ci95}


if __name__ == "__main__":
    main()
