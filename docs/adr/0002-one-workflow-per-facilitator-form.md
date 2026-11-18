# One workflow file per facilitator form

**Status:** accepted, 13 Nov 2026

Each facilitator action (add, award, mark, merge, rename, undo) has its own `facilitator-*.yml`. Each is a few lines that pass its inputs to the shared `facilitator-action.yml`.

We considered a single "Facilitator action" form with an action dropdown and generic fields. We decided against it. The forms are the only interface facilitators see, and per-action field names and descriptions ("The row to keep", "Points (bonus only)") are what make them usable without the docs. The cost of separate files is small: the permissions and plumbing live in `facilitator-action.yml`, and tests fail if the forms' list (`grader/issue_form.py` `FORMS`), their issue templates, the workflow files and the tour's descriptions (`walkthrough/steps.js`) disagree.

Since 16 Nov 2026 facilitators normally use the facilitator page, which sends any number of changes as one *Facilitator: Changes* issue (`leaderboard.py batch`). The per-action forms stay, as the fallback in the Actions tab, and this decision still holds for them.
