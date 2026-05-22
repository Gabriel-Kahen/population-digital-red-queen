# Core War Pilot Setup

This harness is designed to make no paid calls unless explicitly requested.

## Local Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e . google-genai
bash scripts/setup_pmars.sh
```

ADC should point at the trial project:

```bash
gcloud config get-value account
gcloud config get-value project
gcloud auth application-default print-access-token >/dev/null
```

Expected account/project for this machine:

```text
gabekahen2@gmail.com
project-eaa6129b-7991-482e-82e
```

The current corpus has 6 seed warriors and 6 held-out warriors. Validate them
before any paid run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from pdrq.core.types import Program
from pdrq.corewar.mars import MarsConfig, MarsRunner
runner = MarsRunner(MarsConfig(binary=Path("vendor/pmars-bin"), timeout_seconds=5.0))
for directory in [Path("data/corewar/seeds"), Path("data/corewar/heldout")]:
    for path in sorted(directory.glob("*.red")):
        valid, output = runner.validate(Program(path.stem, path.read_text()))
        print(path, "OK" if valid else output)
PY
```

## No-Spend Smoke Test

```bash
.venv/bin/python experiments/run_corewar_pilot.py \
  --conditions linear_drq pop_current pop_archive_niche \
  --generations 1 \
  --candidates 2 \
  --generator stub \
  --run-id smoke
```

## Paid Gemini Smoke Test

Run this only after the no-spend smoke test passes:

```bash
.venv/bin/python experiments/run_corewar_pilot.py \
  --conditions linear_drq \
  --generations 1 \
  --candidates 2 \
  --generator gemini \
  --allow-paid-api \
  --model gemini-2.5-flash \
  --max-llm-calls 2 \
  --max-estimated-cost-usd 1 \
  --run-id gemini_smoke
```

The Gemini wrapper disables thinking for this narrow code-generation call. With
thinking enabled, the model spent most of the output budget before emitting full
Redcode programs.

## Mini Pilot

The first clean paid mini pilot used this shape:

```bash
.venv/bin/python experiments/run_corewar_pilot.py \
  --conditions linear_drq pop_current pop_archive_niche \
  --generations 2 \
  --candidates 5 \
  --generator gemini \
  --allow-paid-api \
  --model gemini-2.5-flash \
  --max-llm-calls 30 \
  --max-estimated-cost-usd 5 \
  --run-id mini_flash_nothink
```

## Full Pilot Shape

Recommended next pass: 720 Gemini calls, three offsets, stricter invalid-output
stopping, and a local `$25` estimated-cost cap. This is still below the
previously discussed `$150` ceiling; raise the cap only after checking the first
large-run summary.

The `linear_drq` condition samples from its archive instead of including the
entire lineage in every prompt. This keeps prompts bounded and reduces repeated
near-identical mutations.

```bash
RUN_ID=pilot_flash_$(date -u +%Y%m%dT%H%M%SZ)
.venv/bin/python experiments/run_corewar_pilot.py \
  --conditions linear_drq pop_current pop_archive_niche \
  --generations 6 \
  --candidates 40 \
  --population-size 6 \
  --opponent-sample 4 \
  --archive-weight 0.35 \
  --offsets 100 500 1500 \
  --match-rounds 20 \
  --generator gemini \
  --allow-paid-api \
  --model gemini-2.5-flash \
  --max-llm-calls 720 \
  --max-estimated-cost-usd 25 \
  --stop-invalid-rate 0.25 \
  --min-candidate-instructions 3 \
  --run-id "$RUN_ID"
```

Afterward, inspect diversity and seed similarity:

```bash
.venv/bin/python experiments/analyze_corewar_run.py "results/corewar_pilot/$RUN_ID"
```

The active local binary is `vendor/pmars-bin`, pMARS 0.9.4 built headless from source. pMARS 0.9.5
was also tested during setup, but the local build hung in this shell on simple
validation commands, so the harness uses the working 0.9.4 binary.

Budgets are alerts, not hard caps. The runner also stops before crossing its
own call and estimated-cost limits.

## Scale-Up Batch

Use the batch runner for the next pass instead of hand-written shell loops. It
assigns every retry a fresh run ID, skips completed seeds, and leaves failed
partial directories untouched for auditing.

Recommended two-axis follow-up:

```bash
BATCH_ID=scaleup_flash_$(date -u +%Y%m%dT%H%M%SZ)

# More independent current-size replicates for variance.
.venv/bin/python experiments/run_corewar_scaleup_batch.py \
  --profile current \
  --batch-id "$BATCH_ID" \
  --replicates 20 \
  --seed-start 101 \
  --parallel 2 \
  --generator gemini \
  --allow-paid-api

# Longer runs to test whether archive/niche improves with search horizon.
.venv/bin/python experiments/run_corewar_scaleup_batch.py \
  --profile long \
  --batch-id "$BATCH_ID" \
  --replicates 10 \
  --seed-start 1001 \
  --parallel 2 \
  --generator gemini \
  --allow-paid-api
```

The `current` profile is 6 generations x 40 candidates x 3 conditions = 720
model calls per replicate. The `long` profile is 12 generations x 40 candidates
x 3 conditions = 1440 calls per replicate. Caps are intentionally local runner
caps: `$2.00` for current-size replicates and `$3.50` for long replicates.

Aggregate completed runs:

```bash
.venv/bin/python experiments/aggregate_corewar_batches.py --batch-id "$BATCH_ID"
```
