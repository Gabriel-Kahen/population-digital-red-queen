#!/usr/bin/env python3
"""Evaluate top generated Core War champions against external benchmarks."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
import textwrap
from dataclasses import asdict
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdrq.core.types import Program  # noqa: E402
from pdrq.corewar.corpus import load_programs  # noqa: E402
from pdrq.corewar.mars import MarsConfig, MarsError, MarsRunner  # noqa: E402
from pdrq.corewar.redcode import dominant_opcode, normalize_source, opcode_counts, static_features  # noqa: E402


DEFAULT_BATCHES = [
    "scaleup_flash_20260515T052028Z",
    "verify_long_20260515T171256Z",
    "verify_long_extra10_20260516T175027Z",
]


def main() -> None:
    args = parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    mars = MarsRunner(
        MarsConfig(
            binary=args.mars_bin,
            rounds=args.match_rounds,
            timeout_seconds=args.match_timeout,
        )
    )

    champions = select_top_champions(args)
    write_champions(champions, out / "champions")

    suites = load_suites(args)
    reference = suites["training_seeds"] + suites["internal_heldout"] + suites["wilkies"] + suites["wilmoo"] + suites["koenigstuhl_94nop_top50"]
    validated = validate_all(mars, champions, suites)
    results = evaluate(mars, champions, validated, args.offsets)
    annotate(champions, reference, results)

    write_outputs(args, out, champions, results, validated)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", action="append", dest="batches", default=[])
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results" / "corewar_benchmarks")
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results" / "corewar_pilot")
    parser.add_argument("--benchmark-dir", type=Path, default=ROOT / "data" / "corewar" / "benchmarks")
    parser.add_argument("--seed-dir", type=Path, default=ROOT / "data" / "corewar" / "seeds")
    parser.add_argument("--heldout-dir", type=Path, default=ROOT / "data" / "corewar" / "heldout")
    parser.add_argument("--mars-bin", type=Path, default=ROOT / "vendor" / "pmars-bin")
    parser.add_argument("--offsets", type=int, nargs="+", default=[100, 500, 1500])
    parser.add_argument("--match-rounds", type=int, default=20)
    parser.add_argument("--match-timeout", type=float, default=10.0)
    parser.add_argument("--random-known-size", type=int, default=50)
    parser.add_argument("--random-known-seed", type=int, default=1776)
    return parser.parse_args()


def select_top_champions(args: argparse.Namespace) -> list[dict[str, object]]:
    batches = args.batches or DEFAULT_BATCHES
    rows: list[dict[str, object]] = []
    seen_sources: set[str] = set()
    for batch in batches:
        for summary in sorted(args.results_dir.glob(f"{batch}_long_s*_a*/summary.json")):
            run_dir = summary.parent
            match = re.search(r"_s(?P<seed>\d+)_a(?P<attempt>\d+)$", run_dir.name)
            data = json.loads(summary.read_text())
            for condition in data["conditions"]:
                champion_id = condition["champion"]
                source_path = find_program(run_dir, champion_id)
                if source_path is None:
                    continue
                source = normalize_source(source_path.read_text(encoding="utf-8", errors="replace"))
                if source in seen_sources:
                    continue
                seen_sources.add(source)
                rows.append(
                    {
                        "program_id": champion_id,
                        "source": source,
                        "source_path": str(source_path),
                        "condition": condition["condition"],
                        "run_id": data["run_id"],
                        "batch_id": batch,
                        "seed": int(match.group("seed")) if match else None,
                        "attempt": int(match.group("attempt")) if match else None,
                        "internal_heldout": float(condition["best_heldout"]),
                        "mean_heldout": float(condition["mean_heldout"]),
                        "population": condition["population"],
                    }
                )
    rows.sort(key=lambda row: float(row["internal_heldout"]), reverse=True)
    return rows[: args.top_n]


def find_program(run_dir: Path, program_id: str) -> Path | None:
    candidates = sorted((run_dir / "programs").glob(f"{program_id}_*.red"))
    return candidates[0] if candidates else None


def load_suites(args: argparse.Namespace) -> dict[str, list[Program]]:
    suites = {
        "training_seeds": load_programs(args.seed_dir),
        "internal_heldout": load_programs(args.heldout_dir, generation=-1, role="heldout"),
        "wilkies": load_programs(args.benchmark_dir / "wilkies", generation=-2, role="wilkies"),
        "wilmoo": load_programs(args.benchmark_dir / "wilmoo", generation=-2, role="wilmoo"),
        "koenigstuhl_94nop_top50": load_programs(args.benchmark_dir / "koenigstuhl_94nop_top50", generation=-2, role="koenigstuhl_94nop_top50"),
        "cgm1_round1": load_programs(args.benchmark_dir / "cgm1_round1", generation=-2, role="cgm1_round1"),
    }
    full = load_programs(args.benchmark_dir / "koenigstuhl_94nop_full", generation=-2, role="koenigstuhl_94nop_full")
    rng = random.Random(args.random_known_seed)
    suites["koenigstuhl_94nop_random50"] = rng.sample(full, k=min(args.random_known_size, len(full)))
    return suites


def validate_all(mars: MarsRunner, champions: list[dict[str, object]], suites: dict[str, list[Program]]) -> dict[str, list[Program]]:
    valid: dict[str, list[Program]] = {}
    for name, programs in suites.items():
        keep = []
        for program in programs:
            ok, _ = mars.validate(program)
            if ok:
                keep.append(program)
        valid[name] = keep
    for champion in champions:
        program = Program(str(champion["program_id"]), str(champion["source"]), metadata={"condition": champion["condition"]})
        ok, output = mars.validate(program)
        champion["valid"] = ok
        champion["validation_output"] = output
    return valid


def evaluate(
    mars: MarsRunner,
    champions: list[dict[str, object]],
    suites: dict[str, list[Program]],
    offsets: list[int],
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    for champion in champions:
        program = Program(str(champion["program_id"]), str(champion["source"]), metadata={"condition": champion["condition"]})
        row: dict[str, object] = {}
        for suite_name, opponents in suites.items():
            print(f"evaluate champion={champion['program_id']} suite={suite_name} opponents={len(opponents)}", flush=True)
            margins = score_details(mars, program, opponents, offsets)
            row[suite_name] = {
                "n_opponents": len(opponents),
                "mean_margin": mean(margins) if margins else None,
                "wins": sum(1 for value in margins if value > 0),
                "losses": sum(1 for value in margins if value < 0),
                "ties": sum(1 for value in margins if value == 0),
                "round_scores": len(margins),
            }
        results[str(champion["program_id"])] = row
    return results


def score_details(mars: MarsRunner, program: Program, opponents: Iterable[Program], offsets: list[int]) -> list[float]:
    margins: list[float] = []
    for opponent in opponents:
        if opponent.program_id == program.program_id:
            continue
        try:
            for result in mars.evaluate(program, opponent, offsets):
                margins.append(result.margin)
        except MarsError:
            margins.append(-1.0)
    return margins


def annotate(champions: list[dict[str, object]], reference: list[Program], results: dict[str, dict[str, object]]) -> None:
    for champion in champions:
        source = str(champion["source"])
        champion["length"] = int(static_features(source)["instruction_count"])
        champion["dominant_opcode"] = dominant_opcode(source)
        champion["archetype"] = infer_archetype(source)
        nearest = nearest_reference(source, reference)
        champion["nearest_reference"] = nearest["program_id"]
        champion["nearest_reference_similarity"] = nearest["similarity"]
        champion["wilkies_score"] = results[str(champion["program_id"])]["wilkies"]["mean_margin"]  # type: ignore[index]
        champion["wilmoo_score"] = results[str(champion["program_id"])]["wilmoo"]["mean_margin"]  # type: ignore[index]
        champion["koenigstuhl_top50_score"] = results[str(champion["program_id"])]["koenigstuhl_94nop_top50"]["mean_margin"]  # type: ignore[index]
        champion["random_known_score"] = results[str(champion["program_id"])]["koenigstuhl_94nop_random50"]["mean_margin"]  # type: ignore[index]
        champion["cgm1_score"] = results[str(champion["program_id"])]["cgm1_round1"]["mean_margin"]  # type: ignore[index]


def infer_archetype(source: str) -> str:
    lower = source.lower()
    counts = opcode_counts(source)
    total = max(1, sum(counts.values()))
    if "ldp" in lower or "stp" in lower:
        return "pspace"
    if "qscan" in lower or "qgo" in lower or (counts["SNE"] + counts["SEQ"]) / total > 0.18:
        return "qscanner/scanner"
    if "imp" in lower or re.search(r"\bmov(?:\.i)?\s+0\s*,\s*1\b", lower):
        return "imp/imp-ring"
    if "paper" in lower or "silk" in lower or (counts["SPL"] / total > 0.18 and counts["MOV"] / total > 0.18):
        return "paper/silk"
    if "vamp" in lower or "pit" in lower or "fang" in lower:
        return "vampire"
    if counts["DAT"] / total > 0.20 and counts["MOV"] / total > 0.15:
        return "stone/clear"
    if counts["SPL"] / total > 0.12:
        return "spl-based hybrid"
    return "unknown/hybrid"


def nearest_reference(source: str, reference: list[Program]) -> dict[str, object]:
    normalized = compact(source)
    best = {"program_id": "", "similarity": 0.0}
    for program in reference:
        similarity = SequenceMatcher(None, normalized, compact(program.source)).ratio()
        if similarity > best["similarity"]:
            best = {"program_id": program.program_id, "similarity": similarity}
    return best


def compact(source: str) -> str:
    lines = []
    for raw in source.splitlines():
        code = raw.split(";", 1)[0].strip().lower()
        if code:
            lines.append(re.sub(r"\s+", " ", code))
    return "\n".join(lines)


def write_champions(champions: list[dict[str, object]], out: Path) -> None:
    if out.exists():
        for path in out.glob("*.red"):
            path.unlink()
    out.mkdir(parents=True, exist_ok=True)
    for index, champion in enumerate(champions, start=1):
        path = out / f"top{index:02d}_{champion['condition']}_{champion['program_id']}.red"
        path.write_text(str(champion["source"]), encoding="utf-8")
        champion["exported_path"] = str(path.relative_to(ROOT))


def write_outputs(
    args: argparse.Namespace,
    out: Path,
    champions: list[dict[str, object]],
    results: dict[str, dict[str, object]],
    suites: dict[str, list[Program]],
) -> None:
    payload = {
        "config": {
            "offsets": args.offsets,
            "match_rounds": args.match_rounds,
            "mars_bin": str(args.mars_bin),
            "random_known_size": args.random_known_size,
            "random_known_seed": args.random_known_seed,
            "batches": args.batches or DEFAULT_BATCHES,
        },
        "suite_sizes_after_validation": {name: len(programs) for name, programs in suites.items()},
        "champions": champions,
        "results": results,
    }
    (out / "benchmark_results.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(champions, out / "champion_benchmark_summary.csv")
    write_latex(champions[:10], ROOT / "paper" / "tables" / "corewar_benchmark_summary.tex")
    write_appendix(champions[:8], ROOT / "paper" / "tables" / "generated_warriors_appendix.tex")


def write_csv(champions: list[dict[str, object]], path: Path) -> None:
    fields = [
        "program_id",
        "condition",
        "run_id",
        "seed",
        "internal_heldout",
        "wilkies_score",
        "wilmoo_score",
        "koenigstuhl_top50_score",
        "random_known_score",
        "cgm1_score",
        "archetype",
        "length",
        "nearest_reference",
        "nearest_reference_similarity",
        "exported_path",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for champion in champions:
            writer.writerow({field: champion.get(field) for field in fields})


def write_latex(champions: list[dict[str, object]], path: Path) -> None:
    lines = [
        "\\begin{tabular}{llrrrrrrrl}",
        "\\toprule",
        "Warrior & Cond. & Len. & Internal & Wilkies & WilMoo & K-Top50 & Rand50 & CGM1 & Archetype \\\\",
        "\\midrule",
    ]
    for champion in champions[:8]:
        lines.append(
            f"{latex_escape(short_id(str(champion['program_id'])))} & "
            f"{latex_escape(short_condition(str(champion['condition'])))} & "
            f"{int(champion['length'])} & "
            f"{float(champion['internal_heldout']):.3f} & "
            f"{float(champion['wilkies_score']):.3f} & "
            f"{float(champion['wilmoo_score']):.3f} & "
            f"{float(champion['koenigstuhl_top50_score']):.3f} & "
            f"{float(champion['random_known_score']):.3f} & "
            f"{float(champion['cgm1_score']):.3f} & "
            f"{latex_escape(str(champion['archetype']))} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_appendix(champions: list[dict[str, object]], path: Path) -> None:
    lines = [
        "% Generated by experiments/benchmark_corewar_champions.py",
    ]
    for index, champion in enumerate(champions, start=1):
        lines.extend(
            [
                f"\\subsection*{{Generated warrior {index}: {latex_escape(str(champion['program_id']))}}}",
                "\\begin{description}",
                f"\\item[Condition] {latex_escape(str(champion['condition']))}",
                f"\\item[Run] {latex_escape(str(champion['run_id']))}, seed {champion['seed']}",
                f"\\item[Scores] internal {float(champion['internal_heldout']):.3f}; Wilkies {float(champion['wilkies_score']):.3f}; WilMoo {float(champion['wilmoo_score']):.3f}; Koenigstuhl Top-50 {float(champion['koenigstuhl_top50_score']):.3f}",
                f"\\item[Archetype] {latex_escape(str(champion['archetype']))}; length {champion['length']}; nearest reference {latex_escape(str(champion['nearest_reference']))} ({float(champion['nearest_reference_similarity']):.3f})",
                "\\end{description}",
                "\\begingroup\\small",
                "\\begin{verbatim}",
                display_source(str(champion["source"])).strip(),
                "\\end{verbatim}",
                "\\endgroup",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def short_id(program_id: str) -> str:
    return program_id.replace("pop_archive_niche", "archive").replace("pop_current", "current").replace("linear_drq", "linear")


def short_condition(condition: str) -> str:
    return condition.replace("pop_archive_niche", "archive").replace("pop_current", "current").replace("linear_drq", "linear")


def display_source(source: str, width: int = 66) -> str:
    """Wrap long source comments for the PDF appendix.

    The exact warriors are exported as .red files; this display transform keeps
    the appendix readable without changing the executable artifacts.
    """
    out: list[str] = []
    for raw in source.splitlines():
        line = raw.rstrip()
        if len(line) <= width:
            out.append(line)
            continue
        if ";" in line:
            code, comment = line.split(";", 1)
            code = code.rstrip()
            prefix = f"{code} ;" if code else ";"
            wrapped = textwrap.wrap(
                comment.strip(),
                width=max(30, width - len(prefix) - 1),
                break_long_words=False,
                break_on_hyphens=False,
            )
            if wrapped:
                out.append(f"{prefix} {wrapped[0]}".rstrip())
                out.extend(f"; {part}" for part in wrapped[1:])
            else:
                out.append(prefix.rstrip())
        else:
            out.extend(
                textwrap.wrap(
                    line,
                    width=width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
                or [line]
            )
    return "\n".join(out)


def latex_escape(value: str) -> str:
    return (
        value.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("$", "\\$")
        .replace("#", "\\#")
        .replace("_", "\\_")
        .replace("{", "\\{")
        .replace("}", "\\}")
    )


if __name__ == "__main__":
    main()
