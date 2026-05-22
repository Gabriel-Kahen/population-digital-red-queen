# Population Digital Red Queen

Research scaffold and manuscript for **Population Digital Red Queen: LLM-Driven
Coevolution in Program Ecosystems**.

This repository intentionally separates:

- `paper/`: the full manuscript draft.
- `src/pdrq/`: reusable algorithm and metric code for population-level Red Queen
  experiments.
- `experiments/`: executable surrogate experiments that validate the algorithm,
  logging, metric, and figure pipeline.

The included surrogate ecology is not a substitute for the full LLM + Core War
experiment. It exists so the machinery can be run end-to-end without an LLM API
key or a MARS/Core War installation.

## Quick Start

```bash
python3 -m unittest discover -s tests
python3 experiments/run_toy_ecology.py
```

The experiment writes summary data to `results/` and figures/tables to
`paper/figures/` and `paper/tables/`.
Use `--seeds`, `--generations`, and `--candidates` for a larger surrogate run.

To build the manuscript with Tectonic:

```bash
tectonic --outdir paper/build paper/main.tex
```

## Core War Pilot Harness

The real Core War pilot setup lives in `docs/PILOT.md`. It uses pMARS through
`vendor/pmars-bin`, Google Vertex AI through ADC, and defaults to a no-spend
stub generator unless `--generator gemini --allow-paid-api` is passed.

No-spend smoke test:

```bash
.venv/bin/python experiments/run_corewar_pilot.py \
  --conditions linear_drq pop_current pop_archive_niche \
  --generations 1 \
  --candidates 2 \
  --generator stub \
  --run-id smoke
```

## External Core War Benchmarks

The paper's Core War credibility checks use external benchmark warriors mirrored
under `data/corewar/benchmarks/`:

- KOTH Wilkies
- KOTH WilMoo
- Koenigstuhl 94nop Top-50
- Koenigstuhl 94nop full archive for deterministic random sampling
- Corewar Global Masters 1 round 1 benchmark

Refresh and rerun the benchmark artifacts with:

```bash
make benchmark-corewar
```

This writes:

- `results/corewar_benchmarks/benchmark_results.json`
- `results/corewar_benchmarks/champion_benchmark_summary.csv`
- `results/corewar_benchmarks/champions/*.red`
- `results/corewar_benchmarks/template_baseline.json`
- `paper/tables/corewar_benchmark_summary.tex`
- `paper/tables/generated_warriors_appendix.tex`

The benchmark replay uses the same pMARS settings as the paper:

```bash
vendor/pmars-bin -b -k -F <offset> -r 20 -s 8000 -c 80000 -p 8000 -l 100 -d 100 red blue
```

It is a fixed-setting replay, not an official Koenigstuhl or KOTH submission.

## Repository Status

The paper is now a results manuscript. It reports a matched-budget Core War
study over 40 long-profile Gemini 2.5 Flash seeds. The main finding is narrow:
archive+niche population search improves best-champion discovery, but it does
not improve mean final-population performance. The added external benchmark
checks also show that the generated champions are not yet competitive against
established Core War benchmark warriors.

## External Feedback

For submission framing, venue fit, reviewer concerns, and a reusable feedback
request note, see `docs/EXTERNAL_FEEDBACK_AND_SUBMISSION.md`.

## Independent Publication

Preprint DOI: [10.5281/zenodo.20349691](https://doi.org/10.5281/zenodo.20349691)

Public release: [v0.1-preprint](https://github.com/Gabriel-Kahen/population-digital-red-queen/releases/tag/v0.1-preprint)

For OSF preprint metadata, release notes, and the GitHub/Zenodo checklist, see:

- `docs/OSF_PREPRINT_METADATA.md`
- `docs/RELEASE_NOTES_v0.1-preprint.md`
- `docs/PUBLICATION_CHECKLIST.md`
