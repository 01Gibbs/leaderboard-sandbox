# One module per check, generic levels included

**Status:** accepted, 13 Nov 2026

A lesson's `check` in `lessons.json` names a module in `grader/checks/`. That is the whole rule, and it holds for the generic levels too: `build.py` and `tests.py` are modules like `fizzbuzz.py`, even though each is only a few lines.

We considered folding `build` and `tests` into `checks/toolkit.py` as built-in levels. We decided against it. Their code would only move, not shrink, and the check registry would need a second way to find a check (built-ins, plus modules), so the interface gets wider. Lesson versions stay correct either way, because every version already covers the toolkit.

Revisit this if there are several generic levels that share most of their code.
