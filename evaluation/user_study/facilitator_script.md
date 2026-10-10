# Facilitator script

Total time: about **35 minutes** per participant. Run one or two participants at a time so the Gemini free tier
is not exhausted (each System analysis uses 2 AI requests). Ideally **prepare the four reports in advance**
(analyse P01, J04, V05, P05 before the sessions) and open them from saved links, so waiting time does not affect
the task times.

## Before the session (5 min)

1. Check `/api/health` shows `"llm": "ok"` (or use pre-generated reports).
2. Prepare the baseline explanations for P01, J04, V05 and P05 (from `run_benchmark.py --conditions baseline`,
   files in `evaluation/results/<run>/baseline/`), printed or opened as plain text.
3. Assign the participant number (P01, P02, …): odd numbers are **Group A**, even numbers **Group B**
   (see `participant_tasks.md`).
4. Have a stopwatch and the response sheet ready.

## Welcome (3 min)

> "Thank you for coming. Today you'll look at four short pieces of code together with an explanation of each,
> and answer three questions about each one. Some explanations come from one tool and some from another. We are
> testing the tools, not you — there are no wrong answers. You can stop at any time."

Give the **consent form**; answer questions; collect the signed form.

## Short introduction to the system (2 min)

> "This website shows a report with five tabs: Overview, Breakdown, Risks, Improved Code and Transparency. Each
> problem shows how serious it is, how confident the tool is, and who found it. Use whatever helps you."

Do **not** explain what the problems in the samples are.

## Tasks (4 × 5 min)

For each task in the participant's order:

1. Open the explanation (system report link or baseline text) and the code. **Start the stopwatch.**
2. The participant answers questions 1–3 of `participant_tasks.md`.
3. **Stop the stopwatch** when question 3 is answered. Record `task_time_s`.
4. Do not help, except to clarify the wording of a question.

After the two System tasks give `questionnaire_explanation.md` (System) and `questionnaire_sus.md`; after the
two Baseline tasks give `questionnaire_explanation.md` (Baseline).

## Debrief (2 min)

> "Thank you. The samples contained deliberately planted weaknesses. Do you have any comments about the tools?"

Write comments in the `comments` column.

## Scoring the answers (after the session)

Record one row per participant × sample in `responses.csv` (copy `responses_template.csv`).

* **comprehension_score** (question 1), against the code's actual purpose:
  * **2** — correct and complete (main purpose and the key operation, e.g. "looks up a user by name in an SQLite
    database").
  * **1** — partly correct (purpose roughly right but vague or missing the key operation).
  * **0** — wrong or no answer.
* **risks_found** — the number of problems the participant listed.
* **risks_correct** — how many of the listed problems match a seeded issue in `benchmark/ground_truth.json`
  (same weakness, roughly the right lines). P01, J04, V05 and P05 each have **1** seeded issue.
* **safety_decision_correct** — **1** if the participant answered "No" (none of the four samples is safe),
  otherwise **0** ("Yes" and "Not sure" are 0).
* **q1–q10** — the explanation questionnaire for that condition (copy the same answers to both rows of that
  condition).
* **sus1–sus10** — only on the System rows.

Then run:

```
python evaluation/scripts/score_user_study.py --responses evaluation/user_study/responses.csv --out evaluation/results/user_study
```
