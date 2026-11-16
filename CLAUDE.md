# Leaderboard: notes for Claude

A workshop leaderboard on GitHub: participants' pull requests on exercise repositories are graded by GitHub Actions, scores live in `participants.csv`, and a static page on GitHub Pages shows them. Python 3 standard library only (`grader/`), plain HTML and JavaScript (`index.html`, `facilitator.html`, `scoring.js`). README.md's "For maintainers" section maps the code.

## Guardrails
- **Participant code runs only in the `grade` job on GitHub Actions.** Locally, grade with `python3 grader/leaderboard.py grade --no-run`, and prove checks against trusted inputs: the exercise's starter and submissions written for the tests.
- **`main` takes changes through pull requests.** The grader and the facilitator workflows push four state files to `main` themselves: `participants.csv`, `grader/results.json`, `grader/history.json`, `grader/batches.json`. Leave them out of pull requests; a grading run after the merge brings them up to date.
- **Scoring rules live once**, in the `RULES` block of `scoring.js`; the page and the grader both read it.

## Lessons
Adding a lesson, or changing how one is graded: use the `add-lesson` skill. A new check is done when `grader/tests/test_checks.py` grades a known-good submission as passing and a known-bad one as failing with its reason, and those tests ran (a JDK is needed; on GitHub Actions they fail rather than skip). `EveryCheckIsTestedTests` fails while a check has no `run_check` test.

## Tests
- Fast tier, about a minute: `GRADER_FAST=1 python3 -m unittest discover grader/tests`.
- Everything (Gradle builds, Docker, workflow simulation): `python3 -m unittest discover grader/tests`.
- Browser journeys: `uv run --no-project --with playwright python -m unittest grader/tests/test_facilitator_browser.py` (once: `uv run --no-project --with playwright playwright install chromium`).
- Lint: `uvx ruff check grader facilitator_walkthrough.py walkthrough.py`.
- Commit with `git -c core.hooksPath=.githooks commit`: the hook lints and runs the fast tier.
- Live, against a real copy on GitHub: `python3 grader/tests/e2e_github.py --repo <owner>/<repo> --all`. It makes real changes and undoes them; use a sandbox copy, never the live leaderboard during a workshop.

## When behaviour changes
Update the words people read, in the same pull request: README.md, FACILITATOR.md, the leaderboard tour (`walkthrough/steps.js`) and the facilitator tour (`walkthrough/facilitator-steps.js`). Tests fail if a tour's `target` is missing from its page. `docs/adr/` holds decisions already made (read before proposing a layout change); `docs/research/` holds dated notes, each with a status line.
