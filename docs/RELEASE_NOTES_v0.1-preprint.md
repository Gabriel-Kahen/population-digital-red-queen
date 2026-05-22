# Release Notes: v0.1-preprint

Initial independent preprint artifact release for:

**Population Digital Red Queen: A Model of LLM-Driven Coevolution in Program Ecosystems**

## Included

- Manuscript source and built PDF.
- Core War pilot and benchmark evaluation code.
- Exact pMARS wrapper settings used by the paper.
- Internal seed and held-out Redcode warriors.
- External benchmark fetch script and benchmark manifest.
- Generated champion Redcode files selected for inspection.
- External benchmark result summaries and tables.
- No-LLM template-mutator baseline.
- Toy ecology implementation and paper figure/table pipeline.
- Submission and external-feedback framing guide.

## Main Result

Across 40 matched long-profile Core War runs using Gemini 2.5 Flash, archive+niche population pressure improved best-champion discovery on the internal evaluation, while linear DRQ had the highest observed mean final-population score.

## Reproducibility

Run:

```bash
python3 -m unittest discover -s tests
tectonic --outdir paper/build paper/main.tex
make benchmark-corewar
```

The external benchmark warriors are third-party Core War programs. They are not relicensed by this project; use `scripts/fetch_corewar_benchmarks.py` to refresh them from their upstream sources.

