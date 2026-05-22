#!/usr/bin/env python3
"""Summarize generated Core War run artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdrq.corewar.redcode import normalize_source, opcode_counts


def main() -> None:
    args = parse_args()
    completions = sorted((args.run_dir / "completions").glob("*.json"))
    if not completions:
        raise SystemExit(f"no completions found under {args.run_dir}")

    seed_sources = {path.stem: normalize_source(path.read_text()) for path in sorted(args.seed_dir.glob("*.red"))}
    rows = []
    sources = []
    for path in completions:
        payload = json.loads(path.read_text())
        source = normalize_source(payload["source"])
        sources.append(source)
        counts = opcode_counts(source)
        instruction_count = sum(counts.values())
        best_similarity, best_seed = max(
            (SequenceMatcher(None, source, seed_source).ratio(), seed_name)
            for seed_name, seed_source in seed_sources.items()
        )
        rows.append(
            {
                "candidate_id": path.stem,
                "instruction_count": instruction_count,
                "line_count": len(source.splitlines()),
                "nearest_seed": best_seed,
                "nearest_seed_similarity": best_similarity,
                "dominant_opcode": counts.most_common(1)[0][0] if counts else "NONE",
            }
        )

    instruction_counts = [row["instruction_count"] for row in rows]
    similarities = [row["nearest_seed_similarity"] for row in rows]
    summary = {
        "run_dir": str(args.run_dir),
        "completions": len(completions),
        "unique_sources": len(set(sources)),
        "instruction_count": _stats(instruction_counts),
        "nearest_seed_similarity": _stats(similarities),
        "high_similarity_over_0_90": sum(1 for value in similarities if value > 0.90),
        "dominant_opcodes": dict(Counter(row["dominant_opcode"] for row in rows)),
        "most_seed_like": sorted(rows, key=lambda row: row["nearest_seed_similarity"], reverse=True)[: args.examples],
        "least_seed_like": sorted(rows, key=lambda row: row["nearest_seed_similarity"])[: args.examples],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--seed-dir", type=Path, default=ROOT / "data" / "corewar" / "seeds")
    parser.add_argument("--examples", type=int, default=8)
    return parser.parse_args()


def _stats(values: list[float]) -> dict[str, float]:
    return {"min": min(values), "mean": mean(values), "max": max(values)}


if __name__ == "__main__":
    main()
