# Could stretch tasks be credited automatically?

*Research note, 18 November 2026. Audience: project lead.*

> **Status (18 Nov 2026).** A proposal; nothing built. Helps and stretch tasks are now counted one per press on the facilitator page, and only bonus points ask for an amount.

## Today
- **Stretch credit has two sources.** The grader gives one, every run, to the authors of the first 3 pull requests on each exercise (`pr_stretch`, worked out from `grader/results.json`; `scoring.js` `RULES` sets the count and the points). A facilitator gives the rest by hand with **+1 stretch** (`stretch`).
- **A stretch task is not something the grader can see.** A lesson's check decides only *correct* or not; nothing in `lessons.json` says what a lesson's stretch tasks are.

## What automating it would take
1. **A lesson says what its stretch tasks are.** For example a `stretch` list in `lessons.json`, each a short name and a test class (or a file) that proves it: `{"name": "Validation errors as JSON", "tests": "src/test/java/StretchValidationTest.java"}`.
2. **The check runs them too.** For a `tests` lesson, after the required tests pass, run each stretch test class on its own; each that passes is a stretch credit for that pull request. A custom check could return them as well.
3. **The board counts them like `pr_stretch`:** worked out by the grader every run (never lowered), shown in a column of their own so a facilitator's `stretch` is never overwritten.

## Cost and judgement
- **It needs the exercise author to write stretch tests**, the same cost as the required tests. The lessons today do not have them.
- **Not every stretch task is testable** (a clear README, a good commit history). Those stay **+1 stretch** by hand.
- **Suggestion:** build it when a lesson with stretch tests exists, starting with the `tests` level, and keep **+1 stretch** for everything else.
