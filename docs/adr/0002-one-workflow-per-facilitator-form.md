# One workflow file per facilitator form

**Status:** accepted, 13 Nov 2026

Each facilitator action (add, award, mark, merge, rename, undo) has its own `facilitator-*.yml`. Each is a few lines that pass its inputs to the shared `facilitator-action.yml`.

We considered a single "Facilitator action" form with an action dropdown and generic fields. We decided against it. The forms are the only interface facilitators see, and per-action field names and descriptions ("The row to keep", "How many helps") are what make them usable without the docs. The cost of separate files is small: the permissions and plumbing live in `facilitator-action.yml`, and tests fail if the walkthrough's list of forms (`walkthrough/steps.js`), the CLI commands and the workflow files disagree.
