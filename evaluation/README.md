# Evaluation toolkit (Chapter Three, Section 3.8 / build spec Section 17)

All commands are run from the repository root with the backend virtual environment
(`backend/.venv/Scripts/python.exe` on Windows, `backend/.venv/bin/python` on Linux/macOS — written `python` below).

## 1. Benchmark dataset

* `benchmark/samples/` — 30 realistic code files (10 Python `P01–P10`, 10 JavaScript `J01–J10`, 10 Java
  `V01–V10`); P10, J10 and V10 are clean.
* `benchmark/ground_truth.json` — the seeded issues: CWE, category, line range and an **anchor** (a code
  fragment that must lie inside the range). Issues marked `"seeded": false` are real but unplanned tool findings.
* Check that every line range is correct:

```
python evaluation/scripts/check_ground_truth.py
```

## 2. Run the benchmark

Dry run without an API key (mock provider — checks that everything works; **not** research results):

```
LLM_PROVIDER=mock python evaluation/scripts/run_benchmark.py --conditions system baseline --runs 2 --out evaluation/results/dry-run
```

PowerShell: `$env:LLM_PROVIDER="mock"; python evaluation\scripts\run_benchmark.py ...`

Real evaluation with Gemini (needs `GEMINI_API_KEY` in `.env`, `LLM_PROVIDER=gemini`):

```
python evaluation/scripts/run_benchmark.py --conditions system baseline --runs 2 --out evaluation/results/2026-10-final
```

* Budget: 30 samples × 2 runs × (2 system requests + 1 baseline request) = **at least 180 Gemini requests**
  (more if repairs happen). The script uses the same per-minute pacer and daily counter as the website.
* If the daily quota runs out the script stops with exit code 2. Run **the same command with `--resume`** after
  midnight Pacific time; finished outputs are skipped.
* Run it when no study participants are using the website.
* Outputs: `system/<ID>_run<N>.json` (full report JSON), `baseline/<ID>_run<N>.txt` (raw text), `manifest.json`
  (provider, model, prompt version, date, git commit, settings).

## 3. Labelling by two reviewers

```
python evaluation/scripts/export_for_labelling.py --results evaluation/results/2026-10-final
```

This creates `labelling.csv`. Two reviewers fill the columns independently (copy the file, one per reviewer, then
merge the `reviewer1_*` / `reviewer2_*` columns):

| item_type | Column | Values |
|---|---|---|
| `ground_truth_issue` | `reviewerN_detected` | 1 = the output identified this seeded issue, 0 = not |
| `claim` | `reviewerN_valid_claim` | 1 = the reported problem is real, 0 = not |
| `explanation` | `reviewerN_correct_explanation` | 0 = wrong, 1 = partly correct, 2 = correct |

## 4. Score the benchmark

```
python evaluation/scripts/score_benchmark.py --results evaluation/results/2026-10-final
```

Writes `metrics.csv`, `metrics.md` (tables for Chapter Four) and `per_sample.csv`:

| Metric | How it is computed |
|---|---|
| Detection rate (recall) | detected seeded issues / seeded issues — system: a finding overlaps the issue lines (±2) with the same CWE (or category when the issue has no CWE); baseline: reviewer labels |
| Precision | findings labelled valid / all findings (reviewer labels; before labelling, an automatic estimate is shown and marked) |
| False alarms on clean samples | findings with severity ≥ MEDIUM on P10, J10, V10 (per run) |
| Explanation correctness | mean reviewer score (0–2) |
| Consistency | mean Jaccard similarity of {(CWE or category, 5-line bucket)} between run 1 and run 2 |
| Transparency completeness | share of outputs that state severity, confidence, limitations and a human-review recommendation |
| Cohen's kappa | agreement between the two reviewers for each labelled column |

## 5. User study

Materials in `user_study/`: `consent_form.md`, `participant_tasks.md` (counterbalanced groups A/B),
`questionnaire_explanation.md`, `questionnaire_sus.md`, `facilitator_script.md` (procedure and scoring rules),
`responses_template.csv`.

Only the prepared benchmark samples are used (the Gemini free tier may use submitted code to improve Google's
products).

Score the responses:

```
python evaluation/scripts/score_user_study.py --responses evaluation/user_study/responses.csv --out evaluation/results/user_study
```

Try the scorer with synthetic data first:

```
python evaluation/scripts/score_user_study.py --synthetic 20 --out evaluation/results/user_study_demo
```

It reports SUS (mean, SD, one-sample t-test against 68), the explanation questionnaire per item and overall, and
task performance (comprehension, risk-identification accuracy, safety decision, time) per condition with
**Wilcoxon signed-rank tests** (paired, α = .05, W, p and effect size r = Z/√N) in `user_study_results.md`.
