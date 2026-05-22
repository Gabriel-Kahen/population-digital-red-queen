#!/usr/bin/env python3
"""Run surrogate Population DRQ experiments and generate paper artifacts."""

from __future__ import annotations

import json
import math
import os
import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt
import numpy as np

from pdrq.algorithms import PopulationConfig, run_linear_drq, run_population_drq, run_static_evolution
from pdrq.metrics import pairwise_diversity, portfolio_score, role_entropy, worst_case_score
from pdrq.toy_ecology import ROLE_NAMES, ROLE_PAYOFFS, ToyCoreWarSurrogate


FIG_DIR = ROOT / "paper" / "figures"
TABLE_DIR = ROOT / "paper" / "tables"
RESULT_DIR = ROOT / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=4, help="number of independent surrogate runs")
    parser.add_argument("--generations", type=int, default=30, help="generations per run")
    parser.add_argument("--candidates", type=int, default=4, help="candidates per generation")
    args = parser.parse_args()

    for path in (FIG_DIR, TABLE_DIR, RESULT_DIR):
        path.mkdir(parents=True, exist_ok=True)

    seeds = list(range(args.seeds))
    generations = args.generations
    candidates = args.candidates
    configs = [
        ("static", None),
        ("linear_drq", None),
        ("pop_current", PopulationConfig("pop_current", generations=generations, candidates_per_generation=candidates)),
        (
            "pop_archive",
            PopulationConfig(
                "pop_archive",
                generations=generations,
                candidates_per_generation=candidates,
                archive_size=96,
                archive_weight=0.45,
            ),
        ),
        (
            "pop_novelty",
            PopulationConfig(
                "pop_novelty",
                generations=generations,
                candidates_per_generation=candidates,
                novelty_weight=0.20,
            ),
        ),
        (
            "pop_niche",
            PopulationConfig(
                "pop_niche",
                generations=generations,
                candidates_per_generation=candidates,
                archive_size=96,
                archive_weight=0.30,
                novelty_weight=0.14,
                niche_protection=True,
                ecological_persistence=True,
                persistence_weight=0.07,
            ),
        ),
    ]

    traces = defaultdict(list)
    for seed in seeds:
        traces["static"].append(run_static_evolution(seed, generations, candidates))
        traces["linear_drq"].append(run_linear_drq(seed, generations, candidates))
        for name, config in configs[2:]:
            traces[name].append(run_population_drq(config, seed))

    summary = summarize(traces)
    (RESULT_DIR / "toy_ecology_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_summary_table(summary, len(seeds))
    figure_algorithm_diagram()
    figure_performance(traces)
    figure_diversity(traces)
    figure_composition(traces["pop_niche"][0])
    figure_payoff_matrix()
    figure_lineage(traces["pop_niche"][0])
    figure_cross_run(traces["pop_niche"])
    figure_archive_tradeoff(seeds, generations, candidates)
    figure_predictive(traces["pop_niche"])


def summarize(traces):
    summary = {}
    for name, runs in traces.items():
        rows = []
        for trace in runs:
            game = ToyCoreWarSurrogate(999)
            heldout = game.heldout_suite()
            final = trace.population
            rows.append(
                {
                    "best_heldout": max(game.score_against(warrior, heldout) for warrior in final),
                    "portfolio": portfolio_score(game, final, heldout),
                    "worst_case": worst_case_score(game, final, heldout),
                    "diversity": pairwise_diversity(final),
                    "entropy": role_entropy(final),
                }
            )
        summary[name] = {
            key: {
                "mean": float(np.mean([row[key] for row in rows])),
                "stderr": float(np.std([row[key] for row in rows], ddof=1) / math.sqrt(len(rows))),
            }
            for key in rows[0]
        }
    return summary


def write_summary_table(summary, seed_count):
    labels = {
        "static": "Static opponent",
        "linear_drq": "Linear DRQ",
        "pop_current": "Population",
        "pop_archive": "Population + archive",
        "pop_novelty": "Population + novelty",
        "pop_niche": "Population + niche",
    }
    lines = [
        f"% Generated from {seed_count} surrogate seeds by experiments/run_toy_ecology.py",
        "\\begin{tabular}{lrrrr}",
        "\\toprule",
        "Method & Best held-out & Oracle portfolio & Diversity & Role entropy \\\\",
        "\\midrule",
    ]
    for key in labels:
        item = summary[key]
        lines.append(
            f"{labels[key]} & "
            f"{fmt(item['best_heldout'])} & "
            f"{fmt(item['portfolio'])} & "
            f"{fmt(item['diversity'])} & "
            f"{fmt(item['entropy'])} \\\\"
        )
    lines.extend(["\\bottomrule", "\\end{tabular}", ""])
    (TABLE_DIR / "pilot_summary.tex").write_text("\n".join(lines), encoding="utf-8")


def fmt(metric):
    return f"{metric['mean']:.3f}$\\pm${metric['stderr']:.3f}"


def series(traces, attr):
    values = []
    for trace in traces:
        values.append([getattr(record, attr) for record in trace.records])
    return np.array(values, dtype=float)


def plot_mean(ax, values, label, color):
    x = np.arange(1, values.shape[1] + 1)
    mean = values.mean(axis=0)
    err = values.std(axis=0, ddof=1) / math.sqrt(values.shape[0])
    ax.plot(x, mean, label=label, color=color, linewidth=2.0)
    ax.fill_between(x, mean - err, mean + err, color=color, alpha=0.16, linewidth=0)


def colors():
    return {
        "static": "#8c8c8c",
        "linear_drq": "#1f77b4",
        "pop_current": "#2ca02c",
        "pop_archive": "#d62728",
        "pop_novelty": "#9467bd",
        "pop_niche": "#ff7f0e",
    }


def figure_algorithm_diagram():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    for ax in axes:
        ax.set_axis_off()
    ax = axes[0]
    ax.set_title("Linear DRQ", fontsize=12, weight="bold")
    xs = np.linspace(0.12, 0.88, 5)
    for i, x in enumerate(xs):
        ax.scatter([x], [0.52], s=520, color="#dbeafe", edgecolor="#2563eb", linewidth=1.5)
        ax.text(x, 0.52, f"$w_{i}$", ha="center", va="center", fontsize=11)
        if i:
            ax.annotate("", xy=(x - 0.07, 0.52), xytext=(xs[i - 1] + 0.07, 0.52), arrowprops=dict(arrowstyle="->", lw=1.3))
    ax.text(0.5, 0.20, "one champion lineage\narchive = previous champions", ha="center", va="center", fontsize=9)

    ax = axes[1]
    ax.set_title("Population DRQ", fontsize=12, weight="bold")
    theta = np.linspace(0, 2 * np.pi, 9)[:-1]
    pts = np.column_stack([0.5 + 0.28 * np.cos(theta), 0.55 + 0.24 * np.sin(theta)])
    for i, (x, y) in enumerate(pts):
        ax.scatter([x], [y], s=320, color="#dcfce7", edgecolor="#16a34a", linewidth=1.3)
        ax.text(x, y, f"$p_{i+1}$", ha="center", va="center", fontsize=9)
    ax.scatter([0.5], [0.55], s=470, color="#fef3c7", edgecolor="#d97706", linewidth=1.4)
    ax.text(0.5, 0.55, "archive\n+niches", ha="center", va="center", fontsize=8)
    ax.text(0.5, 0.17, "many lineages, replacement,\nnovelty, persistence, turnover", ha="center", va="center", fontsize=9)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.86, bottom=0.10, wspace=0.18)
    fig.savefig(FIG_DIR / "fig_algorithm_diagram.pdf")
    plt.close(fig)


def figure_performance(traces):
    fig, ax = plt.subplots(figsize=(7.0, 4.0), constrained_layout=True)
    for name, color in colors().items():
        plot_mean(ax, series(traces[name], "portfolio_heldout"), label=name.replace("_", " "), color=color)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Held-out portfolio score")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    ax.grid(alpha=0.25)
    fig.savefig(FIG_DIR / "fig_pilot_performance.pdf")
    plt.close(fig)


def figure_diversity(traces):
    fig, ax = plt.subplots(figsize=(7.0, 4.0), constrained_layout=True)
    for name, color in colors().items():
        plot_mean(ax, series(traces[name], "diversity"), label=name.replace("_", " "), color=color)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Pairwise behavioral distance")
    ax.legend(frameon=False, fontsize=8, ncol=2)
    ax.grid(alpha=0.25)
    fig.savefig(FIG_DIR / "fig_pilot_diversity.pdf")
    plt.close(fig)


def figure_composition(trace):
    counts = np.array([[record.role_counts[role] for role in ROLE_NAMES] for record in trace.records], dtype=float)
    counts = counts / counts.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(7.2, 4.0), constrained_layout=True)
    role_colors = ["#ef4444", "#3b82f6", "#22c55e", "#a855f7", "#f59e0b", "#64748b"]
    ax.stackplot(np.arange(1, len(counts) + 1), counts.T, labels=ROLE_NAMES, colors=role_colors, alpha=0.90)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Population share")
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, fontsize=8, ncol=3, loc="upper center")
    fig.savefig(FIG_DIR / "fig_pilot_composition.pdf")
    plt.close(fig)


def figure_payoff_matrix():
    fig, ax = plt.subplots(figsize=(5.2, 4.6), constrained_layout=True)
    im = ax.imshow(ROLE_PAYOFFS, cmap="RdBu", vmin=-0.5, vmax=0.5)
    ax.set_xticks(range(len(ROLE_NAMES)), ROLE_NAMES, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(ROLE_NAMES)), ROLE_NAMES, fontsize=8)
    ax.set_title("Surrogate role payoff matrix")
    for i in range(len(ROLE_NAMES)):
        for j in range(len(ROLE_NAMES)):
            ax.text(j, i, f"{ROLE_PAYOFFS[i, j]:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, shrink=0.86, label="row-player margin")
    fig.savefig(FIG_DIR / "fig_payoff_matrix.pdf")
    plt.close(fig)


def figure_lineage(trace):
    warriors = list(trace.all_warriors.values())
    accepted = {record.accepted_id for record in trace.records if record.accepted_id}
    warriors = [w for w in warriors if w.generation >= 0 and (w.warrior_id in accepted or not w.parent_ids)]
    role_to_y = {role: i for i, role in enumerate(ROLE_NAMES)}
    role_colors = dict(zip(ROLE_NAMES, ["#ef4444", "#3b82f6", "#22c55e", "#a855f7", "#f59e0b", "#64748b"]))
    by_id = {w.warrior_id: w for w in warriors}
    fig, ax = plt.subplots(figsize=(7.2, 4.2), constrained_layout=True)
    for warrior in warriors:
        y = role_to_y[warrior.role] + 0.08 * math.sin(hash(warrior.warrior_id) % 97)
        for parent_id in warrior.parent_ids:
            parent = by_id.get(parent_id)
            if parent is None:
                continue
            py = role_to_y[parent.role] + 0.08 * math.sin(hash(parent.warrior_id) % 97)
            ax.plot([parent.generation, warrior.generation], [py, y], color="#94a3b8", alpha=0.30, linewidth=0.7)
        ax.scatter([warrior.generation], [y], s=18, color=role_colors[warrior.role], alpha=0.78)
    ax.set_yticks(range(len(ROLE_NAMES)), ROLE_NAMES)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Role")
    ax.grid(axis="x", alpha=0.20)
    fig.savefig(FIG_DIR / "fig_lineage_tree.pdf")
    plt.close(fig)


def figure_cross_run(runs):
    mat = np.array([[record.role_counts[role] for role in ROLE_NAMES] for trace in runs for record in [trace.records[-1]]], dtype=float)
    mat = mat / mat.sum(axis=1, keepdims=True)
    fig, ax = plt.subplots(figsize=(6.8, 4.0), constrained_layout=True)
    im = ax.imshow(mat, cmap="viridis", vmin=0, vmax=max(0.4, mat.max()))
    ax.set_xlabel("Role")
    ax.set_ylabel("Independent seed")
    ax.set_xticks(range(len(ROLE_NAMES)), ROLE_NAMES, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(runs)), [str(i) for i in range(len(runs))], fontsize=8)
    fig.colorbar(im, ax=ax, label="final population share")
    fig.savefig(FIG_DIR / "fig_cross_run_roles.pdf")
    plt.close(fig)


def figure_archive_tradeoff(seeds, generations, candidates):
    configs = [
        PopulationConfig("archive_0", generations=generations, candidates_per_generation=candidates, archive_size=0, archive_weight=0.0),
        PopulationConfig("archive_24", generations=generations, candidates_per_generation=candidates, archive_size=24, archive_weight=0.25),
        PopulationConfig("archive_96", generations=generations, candidates_per_generation=candidates, archive_size=96, archive_weight=0.45),
        PopulationConfig("archive_full", generations=generations, candidates_per_generation=candidates, archive_size=10_000, archive_weight=0.70),
    ]
    xs, ys, labels = [], [], []
    for config in configs:
        divs, ports = [], []
        for seed in seeds[:8]:
            trace = run_population_drq(config, seed + 100)
            game = ToyCoreWarSurrogate(999)
            heldout = game.heldout_suite()
            divs.append(pairwise_diversity(trace.population))
            ports.append(portfolio_score(game, trace.population, heldout))
        xs.append(float(np.mean(divs)))
        ys.append(float(np.mean(ports)))
        labels.append(config.name.replace("_", " "))
    fig, ax = plt.subplots(figsize=(5.6, 4.1), constrained_layout=True)
    ax.plot(xs, ys, color="#334155", linewidth=1.1)
    ax.scatter(xs, ys, s=70, color="#0f766e")
    for x, y, label in zip(xs, ys, labels):
        ax.text(x + 0.01, y, label, fontsize=8, va="center")
    ax.set_xlabel("Final behavioral diversity")
    ax.set_ylabel("Held-out portfolio score")
    ax.grid(alpha=0.25)
    fig.savefig(FIG_DIR / "fig_archive_tradeoff.pdf")
    plt.close(fig)


def figure_predictive(runs):
    rows = []
    for trace in runs:
        final_ids = set(trace.records[-1].population_ids)
        for warrior in trace.all_warriors.values():
            if warrior.generation < 1:
                continue
            rows.append((warrior.descriptor(), warrior.role, float(warrior.warrior_id in final_ids)))
    x = np.array([row[0] for row in rows], dtype=float)
    y_persist = np.array([row[2] for row in rows], dtype=float)
    y_role = np.array([ROLE_NAMES.index(row[1]) for row in rows], dtype=int)

    rng = np.random.default_rng(123)
    idx = rng.permutation(len(rows))
    split = int(0.70 * len(rows))
    train, test = idx[:split], idx[split:]
    persist_auc = simple_auc(linear_scores(x[train], y_persist[train], x[test]), y_persist[test])
    role_acc = nearest_centroid_accuracy(x[train], y_role[train], x[test], y_role[test])

    fig, ax = plt.subplots(figsize=(5.2, 3.6), constrained_layout=True)
    labels = ["role membership", "ecological persistence"]
    values = [role_acc, persist_auc]
    ax.bar(labels, values, color=["#2563eb", "#dc2626"], alpha=0.86)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Toy predictive score")
    ax.grid(axis="y", alpha=0.22)
    fig.savefig(FIG_DIR / "fig_predictive_pilot.pdf")
    plt.close(fig)


def linear_scores(x_train, y_train, x_test):
    x_train = np.column_stack([np.ones(len(x_train)), x_train])
    x_test = np.column_stack([np.ones(len(x_test)), x_test])
    reg = 0.05 * np.eye(x_train.shape[1])
    beta = np.linalg.solve(x_train.T @ x_train + reg, x_train.T @ y_train)
    return x_test @ beta


def simple_auc(scores, labels):
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    comparisons = [(p > n) + 0.5 * (p == n) for p in pos for n in neg]
    return float(np.mean(comparisons))


def nearest_centroid_accuracy(x_train, y_train, x_test, y_test):
    centroids = []
    classes = sorted(set(y_train.tolist()))
    for cls in classes:
        centroids.append(x_train[y_train == cls].mean(axis=0))
    centroids = np.array(centroids)
    preds = []
    for row in x_test:
        preds.append(classes[int(np.argmin(np.linalg.norm(centroids - row, axis=1)))])
    return float(np.mean(np.array(preds) == y_test))


if __name__ == "__main__":
    os.environ.setdefault("MPLBACKEND", "Agg")
    main()
