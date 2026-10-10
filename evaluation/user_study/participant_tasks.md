# Participant tasks

The study compares two conditions using a **within-subjects** design:

* **System** — the Explainable AI Code Review Assistant report (all five tabs).
* **Baseline** — a plain AI explanation of the same code (the output of `baseline_user.txt`, printed or shown as
  plain text).

Each participant does **both** conditions, with the order and sample pairs **counterbalanced**:

| Group | Task 1 | Task 2 | Task 3 | Task 4 |
|---|---|---|---|---|
| **A** (odd participant numbers) | System on **P01** | Baseline on **J04** | System on **V05** | Baseline on **P05** |
| **B** (even participant numbers) | Baseline on **P01** | System on **J04** | Baseline on **V05** | System on **P05** |

P01/J04 are SQL-injection samples (Python / JavaScript); V05/P05 are path-traversal samples (Java / Python), so
each pair has comparable difficulty.

---

## For every sample

Read the code and the explanation you are given, then answer:

1. **In one or two sentences, what does this code do?**

   ___________________________________________________________________________

2. **List the problems you found (give line numbers if possible).**

   ___________________________________________________________________________

3. **Is this code safe to use as it is?** ☐ Yes ☐ No ☐ Not sure — **Why?**

   ___________________________________________________________________________

The facilitator records the **time** you spend on each sample (from opening the explanation to finishing
question 3).

---

## After the System tasks

Fill in **questionnaire_explanation.md** for the System, and **questionnaire_sus.md** (usability) once.

## After the Baseline tasks

Fill in **questionnaire_explanation.md** for the Baseline.
