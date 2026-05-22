.PHONY: benchmarks benchmark-corewar paper test

benchmarks:
	python3 scripts/fetch_corewar_benchmarks.py

benchmark-corewar: benchmarks
	.venv/bin/python experiments/benchmark_corewar_champions.py --top-n 10 --match-rounds 20 --match-timeout 3 --offsets 100 500 1500
	.venv/bin/python experiments/run_corewar_template_baseline.py

paper:
	tectonic --outdir paper/build paper/main.tex

test:
	.venv/bin/python -m unittest discover -s tests
