# Maintaining the leaderboard

For whoever changes the code. [CLAUDE.md](../CLAUDE.md) holds the rules of the house for Claude Code; [TAKEOVER.md](TAKEOVER.md) covers who does what and moving it; `docs/adr/` records decisions already made (read them before proposing a layout change); `docs/research/` holds dated notes on why things are the way they are.

## The code
Python 3 standard library only, in `grader/`, and plain HTML and JavaScript at the top.

| File | What it owns |
|---|---|
| `scoring.js` | The rules (points, status words, how the CSV is read): the only scoring code. `grader/rules.py` reads its `RULES` block, and a test runs both on tricky files to prove they agree. |
| `grader/lessons.py` | Loading and checking `lessons.json`, each lesson's check, test files and version (changing one regrades only it), and every write to `lessons.json`. A lesson with `"status": "checking"` is left out of everything but `load(checking=True)`. |
| `grader/lesson_lifecycle.py` | A lesson's life, the one place that decides it: `add-lesson` and `remove-lesson` (generic levels only, saved as checking), which lessons grading tries (through a seam: `trial.run`, or practice's pretend trial), and which go live. |
| `grader/exercise_tests.py` | Pinning a lesson's tests from a public repository at one commit: plain files only, inside the fetched repository, at most 500 files and 5 MB. |
| `grader/trial.py` | Trying a checking lesson in the grading job's sandbox: the starter compiles with the pinned tests; a solutions repository passes them. |
| `grader/grade.py` | Listing pull requests and grading the ones that need it; trying checking lessons. |
| `grader/submissions.py` | `grader/results.json`: each pull request's result, trials, the early-PR bonus. Validated before use. |
| `grader/roster.py` | Every change to `participants.csv`: facilitator actions, undo, applying graded results (only ever up) and putting a lesson whose trial passed live. |
| `grader/executor.py` | The only way participant code runs: a clean environment, timeouts, clean-up, the CI sandbox user, and `fetch`. |
| `grader/checks/` | One module per check (`build`, `tests`, and each custom check), built from `toolkit.py`. |
| `grader/leaderboard.py` | The command line, the same commands the workflows run; settles each facilitator change as changed, refused or broken. |
| `grader/issue_form.py` | Facilitator issues: who may (write, maintain or admin), the command each form or batch asks for, and the answer. |
| `facilitator.html`, `github-reader.js` | The facilitator page (two tabs, one Changes box) and its one way of reading GitHub without a token: conditional reads, one budget of 50 an hour, polls spaced to share it, waiting out GitHub's limit. |
| `changes.js` | The Changes box without the page: what waits (no duplicates, at most 40), one issue per Send trimmed to fit GitHub's address, and each row's outcome from `grader/batches.json`, or giving up after a while (never while GitHub limits reads). Tested in Node (`test_changes_box.py`); its issue text matches `issue_form.batch_body`. |
| `facilitator_walkthrough.py`, `walkthrough.py`, `walkthrough/` | The two tours, on practice copies; `data-tour` attributes link each step to the page, and tests fail if one goes missing. |

## How a facilitator change travels
The page's **Send** opens `.github/ISSUE_TEMPLATE/facilitator-changes.yml` filled in with every waiting change, one JSON row per line. `changes-from-issues.yml` checks the author's permission, runs `leaderboard.py batch` through `facilitator-action.yml` (each row's outcome to `grader/batches.json`, each change with an id to `grader/history.json`), then answers, closes and locks the issue. The page follows by reading those two files. The per-action forms in the Actions tab do the same one change at a time.

## How a lesson goes live
`add-lesson` saves it as checking, with its tests pinned. That push starts *Grade submissions*, whose grade job tries it (`trial.py`) and whose publish job puts it live when its trial passed at its current version (`lesson_lifecycle.version`; `grader/lesson_lifecycle.py` is the one place these rules live), which starts grading once more for its pull requests. A failed trial is kept in `results.json` with its reasons, and tried again a day later or when the lesson changes.

## Tests
- `GRADER_FAST=1 python3 -m unittest discover grader/tests`: the fast tier, about a minute.
- `python3 -m unittest discover grader/tests`: everything, including Gradle builds, Docker and `simulate_workflows.py` (every workflow's shell steps against a scratch repository). It needs a JDK and network access; on GitHub Actions a starter that cannot be cloned fails the run rather than skipping.
- `uv run --no-project --with playwright python -m unittest grader/tests/test_facilitator_browser.py`: the facilitator page's journeys in Chromium, on the practice copy.
- `python3 grader/tests/mutate.py <module> --tests <test modules>`: mutation testing; `mutation.yml` runs it for the core modules.
- `python3 grader/tests/e2e_github.py --repo <owner>/<repo> --all`: every real workflow on a sandbox copy on GitHub, undone afterwards, with its issues and runs deleted when everything passed. `--lessons` adds and removes a lesson.
- Commit with `git -c core.hooksPath=.githooks commit` to lint and run the fast tier first. *Test the grader* runs both tiers and `ruff` on every pull request.

## Security
Pull-request code runs only in the grading job: a read-only token, no secrets, as a separate `grader-sandbox` user that cannot write to the grader or its results, and everything it started is killed after each check. A lesson's trial runs there too. Saving happens in separate jobs that run no participant code, refuse a malformed `results.json`, and push with the deploy key: no workflow's token can write to the repository. Tests enforce this: `test_boundaries.py` (where processes may start) and `test_workflows.py` (permissions, inputs never reaching a shell, actions pinned to commits). Locally, grade only with `leaderboard.py grade --no-run`.
