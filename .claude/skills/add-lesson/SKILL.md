---
name: add-lesson
description: Add a workshop lesson (an exercise repository people open pull requests against) to the leaderboard, or change how much of a lesson is graded automatically.
---

# Add a lesson

A **lesson** is one entry in `lessons.json`: a repository whose pull requests are submissions, shown as one column on the page. Adding a lesson is plug-and-play: the page, the CSV column and the facilitator forms all follow from that entry. Only the **check** (how "correct" is decided) needs thought.

**Guardrail:** pull-request code runs only inside the GitHub Actions `grade` job. Locally, use `grade --no-run` and test checks against trusted inputs (the lesson's starter and reference submissions you write); a pull request's checkout is never built or run on this machine.

## Levels

Pick the lowest level that decides "correct" honestly. Every level counts any pull request as *submitted*.

| `check` | Correct when | You write |
|---|---|---|
| `none` | a facilitator marks it (facilitator page: pick the person, **Mark correct**) | nothing |
| `build` | the submission's Gradle project builds | nothing |
| `tests` | our tests pass against the submission | nothing, when the exercise repository ships the tests a participant must make pass: `python3 grader/leaderboard.py pin-tests <key>` copies them into `grader/fixtures/<key>/` and records `tests_commit`. Otherwise, test files in `grader/fixtures/<key>/`, at the same paths as in the project (they overwrite the submission's copies) |
| custom | anything else: calling the running app, inspecting a Dockerfile, planted-bug tests | a module `grader/checks/<key>.py` |

The existing custom checks in `grader/checks/` (`rest_api.py`, `framework_upgrade.py`, `container_image.py`, `fizzbuzz.py`) are the patterns to copy, built from `grader/checks/toolkit.py` (`gradle_project`, `gradle`, `overlay`, `employee_api_checks`, and `RunningApp` with its `Jar` and `Container` adapters for calling a running app). Participant code runs only through the workspace (`ws.run`, `ws.start`), which handles the CI sandbox and clean-up; the one exception is a container image, which `Container` runs with Docker. A test (`grader/tests/test_boundaries.py`) fails if a check starts processes any other way, or imports grader modules other than its toolkit.

## Steps

1. **Read the lesson.** Fetch the repository's problem statement or README (`gh api repos/<owner>/<repo>/contents/...`) and list its pull requests (`gh pr list -R <owner>/<repo> --state all`) to see where submissions put their work. Done when you can state in one sentence what a correct submission does, every requirement in the problem statement is either something a check can observe or something only a human can judge, and the repository is public (the grader reads it without a token; `gh api repos/<owner>/<repo> --jq .visibility`).

2. **Agree the level** with the user: propose one from the table with the reason. Try `tests` with `pin-tests` first when the repository has `src/test/` that defines "correct"; it does not fit an exercise where writing the tests is the task (FizzBuzz) or a repository with no project yet (REST API). Name any requirement it will not check. Done when the user has confirmed it.

3. **Add the entry** to `lessons.json`: `key` (lowercase, digits, `_`; becomes the CSV column), `label` (shown on the page), `repo` (`owner/name`), `check`. Done when `python3 -m unittest discover grader/tests -p test_lessons.py` passes (it validates the real `lessons.json`).

4. **Write the check** for `tests` or custom. To use the repository's own tests, add the entry with `"check": "none"` and run `python3 grader/leaderboard.py pin-tests <key>` (add a full commit id to pin an older commit): it copies them, sets `check` to `tests` and records `tests_commit`; go on to step 5. Otherwise: Every failure reason is a sentence the participant can act on ("POST with a blank name should return 400 (got 500)"). A custom check is a new module `grader/checks/<name>.py` (the name used as `check` in `lessons.json`) with `def check(ws, lesson)` (the checkout is at `ws.path`, the lesson's test files at `lesson.test_files`) returning `(passed, reasons)` or raising `CheckFailed`. Keep its constants in that module, not in the toolkit: then editing it regrades only its own lessons. The module is found by its file name; nothing else to register. Done when every requirement from step 1 that a check can observe is checked.

5. **Prove it** in `grader/tests/test_checks.py`, following `GradleCheckTests` and its `run_check` helper (it grades a folder through `grade.grade_submission`, exactly as real pull requests are graded): at least one known-good submission passes and one known-bad submission fails with the specific reason, starting from the exercise's starter (add it to `STARTERS`) and the reference submission's files, kept in `grader/tests/data/<key>/` so the tests never depend on a solution repository staying public. Cover a half-done submission too: it fails naming only what is left. Done when `python3 -m unittest discover grader/tests` is green with your new tests running, not skipped. A JDK is needed; if none is installed, download a Temurin JDK into a scratch folder and point `JAVA_HOME_21_X64` (or `_ARM64`) at it.

6. **Pull request:** on a branch, commit `lessons.json`, the check, its fixtures and tests, and README.md's list of custom checks; leave `participants.csv` and `grader/*.json` out (the workflows write those on `main`). Open a pull request: main only takes changes through one. Done when both CI checks (`fast` and `slow`) pass and it is merged. Then run *Grade submissions* (`gh workflow run grade.yml`): one run records every existing submission and grades it. Done when its run succeeds and `participants.csv` on `main` has the new column.

7. **Optionally connect the repository** so each pull request is graded within a minute: only if the user owns it, they run `grader/setup-pr-trigger.sh` (a wizard; it needs them in a browser and admin access to the exercise repository, so never run it yourself). Without it the lesson is graded once a day, or when a facilitator presses **Grade now**; that is the normal setup.

8. **Hand over:** tell the user what level the lesson is on, what it does not check, and that real grading happens at the next daily run, or now with **Grade now** on the facilitator page. For `none`, remind them facilitators mark results on the facilitator page (pick the person, **Mark correct**).
