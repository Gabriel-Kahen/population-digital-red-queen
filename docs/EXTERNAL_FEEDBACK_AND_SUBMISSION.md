# External Feedback and Submission Framing

This document is the reviewer-facing packaging guide for the current draft of
`paper/main.tex`. It is not a new experiment plan. The goal is to make the paper
easy to send to external readers without overstating what the results prove.

## Current Status

The paper is ready for external feedback as a careful empirical study about
LLM-driven adversarial search dynamics. It is not ready to be framed as a
competitive Core War result.

The strongest defensible claim is:

> Under a matched Gemini 2.5 Flash call budget, archive+niche population
> pressure improved best-champion discovery on the internal Core War evaluation,
> but did not improve mean final-population performance and did not produce
> externally competitive warriors against established Core War benchmarks.

That framing should appear in any cover note, abstract, talk, or submission
summary. It is more credible than claiming that PDRQ evolves strong Core War
warriors.

## One-Paragraph External Pitch

This paper studies whether LLM-driven adversarial program evolution changes when
the evolving object is a population rather than a single champion. It introduces
Population Digital Red Queen, motivates it with finite-game examples, and tests
three matched-budget variants in Core War using Gemini 2.5 Flash. Across 40
long-profile runs, archive+niche pressure improves the average best champion
found, but does not improve the mean quality of the final live population.
External benchmark checks against Wilkies, WilMoo, Koenigstuhl 94nop, and CGM1
show that the generated warriors are not hill-competitive. The contribution is
therefore about search dynamics and evaluation discipline, not about producing
elite Redcode.

## Claims to Emphasize

- Population state is a different dynamical model from single-lineage self-play.
- In finite non-transitive games, portfolio value and champion value can diverge.
- In the Core War experiment, archive+niche pressure improved best-champion
  discovery under a fixed LLM budget.
- Mean final-population quality did not improve; linear DRQ had the highest
  observed mean on that metric.
- External Core War benchmarks were negative, and that result is part of the
  contribution because it prevents overclaiming.
- The paper includes exact pMARS settings, generated warrior listings, benchmark
  artifacts, and rerun commands.

## Claims to Avoid

- Do not say the generated warriors are competitive Core War warriors.
- Do not say PDRQ dominates linear DRQ.
- Do not say the final population is a deployable robust portfolio.
- Do not treat the six-warrior internal held-out suite as a real Core War
  benchmark.
- Do not imply the fixed-setting Koenigstuhl replay is an official Koenigstuhl
  rank or KOTH submission.
- Do not describe heuristic archetype labels as a full behavioral taxonomy.

## Best Initial Feedback Readers

Ask for feedback from three kinds of readers, in this order:

1. A Core War specialist who can judge the Redcode, pMARS settings, benchmark
   framing, and whether the generated warriors look trivial, derivative, or
   evaluator-specific.
2. An evolutionary computation or artificial life researcher who can judge the
   PDRQ framing, finite-game argument, and population-vs-champion distinction.
3. An ML program-search researcher who can judge the LLM search protocol,
   matched-budget design, and statistical interpretation.

The most important first feedback is from Core War readers, because they are the
most likely to catch credibility issues in benchmark setup, dialect assumptions,
or Redcode interpretation.

## Venue Fit

Venue fit depends on the intended framing. Deadlines and track details change,
so verify current calls before submitting. The notes below are about intellectual
fit, not a guarantee that a 2026 deadline is still open.

### Strong Fit: Artificial Life / Evolutionary Computation

The best intellectual fit is artificial life or evolutionary computation,
especially if the submission foregrounds population dynamics, non-transitive
games, and LLMs as mutation operators.

Good targets or communities to watch:

- ALIFE (https://2026.alife.org/): strong conceptual fit for digital organisms, artificial ecosystems,
  and adaptive systems. The 2026 ALIFE site frames the conference around
  "Living and Lifelike Complex Adaptive Systems."
- GECCO (https://gecco-2026.sigevo.org/): strong fit for genetic and evolutionary computation, especially as a
  late-breaking abstract, workshop paper, or evolutionary machine learning
  contribution if the main full-paper deadline is not available.
- EvoStar / EuroGP / EvoApplications (https://www.evostar.org/2026/): strong fit if framed as genetic
  programming, evolutionary program search, or evolutionary machine learning.

### Possible Fit: ML Program Search / LLM Agents Workshops

This could fit workshops around LLM agents, program synthesis, open-endedness,
or automated discovery. For those venues, emphasize the methodology:

- LLM as semantic mutation operator.
- Self-generated adversarial training distribution.
- Matched-budget comparison across search algorithms.
- Negative external benchmark as a reliability check.

The paper is probably too narrow for a top-tier ML main conference unless it is
expanded with broader domains or a substantially stronger benchmark story.

### Weak Fit: Core War as a Competitive Result

Do not submit or present this primarily as "new strong Core War warriors." The
external benchmark results do not support that. A Core War audience may still
find it interesting as:

- an LLM-generated Redcode case study;
- a comparison of internal search pressure versus external benchmark strength;
- a transparent negative result showing how easily small held-out suites can
  overstate warrior quality.

## Suggested Cover Note for External Feedback

Subject: Feedback request: LLM-driven Core War search paper

Hi [Name],

I am looking for critical feedback on a draft about LLM-driven adversarial
program evolution in Core War. The paper introduces a population variant of
Digital Red Queen and reports a matched-budget Gemini 2.5 Flash experiment.

The main result is deliberately narrow: archive+niche population pressure
improves best-champion discovery on the internal evaluation, but does not
improve mean final-population quality. External benchmark checks against
Wilkies, WilMoo, Koenigstuhl 94nop, and CGM1 are negative, so the paper does not
claim that the generated warriors are hill-competitive.

I would especially value feedback on whether the Core War framing, pMARS
settings, benchmark interpretation, and Redcode listings are credible to someone
who knows the community.

Draft PDF: `paper/build/main.pdf`
Artifact checklist: Appendix B of the paper and `docs/EXTERNAL_FEEDBACK_AND_SUBMISSION.md`

Thank you,
[Name]

## Reviewer-Facing Checklist

Before sending the paper externally, confirm:

- The latest PDF builds from `paper/main.tex`.
- The abstract says the external benchmark replay is negative.
- The Core War experiment section states pMARS version, dialect, core size,
  cycle limit, process limit, maximum warrior length, rounds, offsets, and
  validation command.
- The benchmark table includes internal held-out, Wilkies, WilMoo, Koenigstuhl
  Top-50, random Koenigstuhl sample, CGM1, archetype, and length.
- The appendix includes generated warrior listings and exact artifact paths.
- The README tells readers how to rerun `make benchmark-corewar`.
- The manuscript does not claim hill competitiveness, official Koenigstuhl
  ranking, or deployable portfolio robustness.

## Likely Reviewer Concerns and Responses

**Concern: the internal held-out suite is tiny.**

Correct. The paper now treats it as an internal search diagnostic and uses
external benchmarks as a credibility check.

**Concern: the generated warriors are not strong.**

Correct. The claim is about search dynamics under LLM generation, not about
competitive Redcode. The negative external benchmark result is reported
directly.

**Concern: the archetype labels are heuristic.**

Correct. They are used only as inspection aids. A full behavioral taxonomy would
need trace- or payoff-based clustering.

**Concern: fixed offsets are not a full hill protocol.**

Correct. The paper states that the external replay is not an official
Koenigstuhl or KOTH submission.

**Concern: the LLM might be copying simple seed patterns.**

Partly true. The nearest-source audit reports source similarity, including one
high internal scorer close to the seed `paper`. This weakens novelty claims but
strengthens the paper's honesty.

## Next Edit If a Venue Requires Shortening

If page limits force cuts, preserve these sections:

- Abstract.
- Contributions.
- Core War Experiment.
- External Core War benchmarks.
- Core War validity checks.
- Results and interpretation.
- Threats to Validity.
- Reproducibility Artifact Checklist.

Cut or compress first:

- Some finite-game proof detail.
- Most surrogate figures.
- Full generated warrior listings, moving them to repository artifacts.
