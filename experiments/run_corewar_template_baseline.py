#!/usr/bin/env python3
"""Small no-LLM Core War template-mutator baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pdrq.core.types import Program  # noqa: E402
from pdrq.corewar.corpus import load_programs  # noqa: E402
from pdrq.corewar.mars import MarsConfig, MarsError, MarsRunner  # noqa: E402
from pdrq.corewar.redcode import normalize_source  # noqa: E402


def main() -> None:
    out = ROOT / "results" / "corewar_benchmarks"
    out.mkdir(parents=True, exist_ok=True)
    mars = MarsRunner(MarsConfig(binary=ROOT / "vendor" / "pmars-bin", rounds=20, timeout_seconds=3.0))
    heldout = load_programs(ROOT / "data" / "corewar" / "heldout", generation=-1, role="heldout")
    suites = {
        "wilkies": load_programs(ROOT / "data" / "corewar" / "benchmarks" / "wilkies", role="wilkies"),
        "wilmoo": load_programs(ROOT / "data" / "corewar" / "benchmarks" / "wilmoo", role="wilmoo"),
        "koenigstuhl_94nop_top50": load_programs(ROOT / "data" / "corewar" / "benchmarks" / "koenigstuhl_94nop_top50", role="koenigstuhl_94nop_top50"),
    }
    candidates = [template_bomber(i) for i in range(1, 51)]
    rows = []
    for candidate in candidates:
        internal = score(mars, candidate, heldout)
        rows.append({"program": candidate, "internal_heldout": internal})
    rows.sort(key=lambda row: row["internal_heldout"], reverse=True)
    best = rows[0]
    program = best["program"]
    result = {
        "program_id": program.program_id,
        "internal_heldout": best["internal_heldout"],
        "source": program.source,
        "suites": {name: score(mars, program, opponents) for name, opponents in suites.items()},
        "candidate_count": len(candidates),
    }
    (out / "template_baseline.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (out / "template_baseline.red").write_text(program.source)
    write_table(result, ROOT / "paper" / "tables" / "corewar_template_baseline.tex")
    print(json.dumps({k: v for k, v in result.items() if k != "source"}, indent=2, sort_keys=True))


def template_bomber(index: int) -> Program:
    step = [1, 2, 4, 5, 7, 9, 11, 13, 17, 23][index % 10]
    ptr = 40 + index * 137 % 3900
    source = f""";redcode-94
;assert 1
;name Template Bomber {index}
;author deterministic no-LLM baseline
;strategy simple add/mov bomber template
        org start
start   add #{step}, ptr
        mov bomb, @ptr
        jmp start
bomb    dat #0, #0
ptr     dat #0, #{ptr}
        end start
"""
    return Program(f"template_bomber_{index:02d}", normalize_source(source))


def score(mars: MarsRunner, program: Program, opponents: list[Program]) -> float:
    margins = []
    for opponent in opponents:
        try:
            for result in mars.evaluate(program, opponent, [100, 500, 1500]):
                margins.append(result.margin)
        except MarsError:
            margins.append(-1.0)
    return mean(margins) if margins else 0.0


def write_table(result: dict[str, object], path: Path) -> None:
    suites = result["suites"]
    assert isinstance(suites, dict)
    lines = [
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "Baseline & Internal & Wilkies & WilMoo & K-Top50 \\\\",
        "\\midrule",
        f"Template bomber best-of-50 & {float(result['internal_heldout']):.3f} & {float(suites['wilkies']):.3f} & {float(suites['wilmoo']):.3f} & {float(suites['koenigstuhl_94nop_top50']):.3f} \\\\",
        "\\bottomrule",
        "\\end{tabular}",
    ]
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
