# Java Exercise Leaderboard

A public leaderboard for the workshop. Participants submit each exercise as a pull request; the leaderboard picks them up, grades them, and ranks everyone by points. Facilitators adjust scores from GitHub's **Actions** tab, with nothing to install.

**New here? Start with the walkthrough.** In this folder, run `python3 walkthrough.py` (Windows: `py walkthrough.py`; Python 3.8 or newer). It opens a five-minute guided tour of the leaderboard in your browser: what people see, how scores get there, the facilitator forms, and what a workshop repo needs. It only runs on your computer; press Ctrl+C to stop.

- **Facilitators:** everything you need is in [FACILITATOR.md](FACILITATOR.md).
- **Project lead:** set it up once (below), then add lessons as the workshop grows.

## How it works

```
participant opens a PR ──► "Grade submissions" (every 4 hours) ──► participants.csv ──► public page
                                                                        ▲
facilitator fills in a form in the Actions tab (award, merge, undo...) ─┘
```

1. **Submissions.** Every 4 hours (or straight away, when a facilitator runs it), the *Grade submissions* workflow lists the pull requests on each lesson's repository (listed in [`lessons.json`](lessons.json)). Each author is a participant: anyone new gets a row, named from their GitHub profile, and the exercise shows as *Submitted*. Pull requests from the repository's owner, from bots, and ones closed without merging are not submissions.
2. **Grading.** Each pull request's latest commit is checked once, with the grader's own tests (so editing the tests in a pull request does not help). If it passes, the exercise shows as *Correct*. The reason for every pass or fail is kept in `grader/results.json`.
3. **Facilitator changes** (points, names, merges, undo) are forms in the Actions tab. Each one logs the rows it changed, before and after, in `grader/history.json`, so undo can change back exactly the cells it touched. Changes made at the same moment all land: each run applies its change to the latest version and retries if someone else saved first.
4. **The page** (`index.html`, served by GitHub Pages) reads `participants.csv`, `lessons.json` and `dashboard.json` (title, workshops, next week's plan, kudos), and updates a minute or two after any change.

The grader never lowers a result, so a facilitator's changes are never overwritten by the next grading run.

## Points
Submitted **10**, correct **30**, each stretch credit **+5**, each time helping a colleague **+5**, plus any bonus points a facilitator gives. The first **3** pull requests on each exercise earn their authors a stretch credit each (the `pr_stretch` column, worked out by the grader on every run; don't edit it). Equal points share a rank; within it, people with more correct exercises are listed first. They live in one place, the `RULES` block at the top of `scoring.js`, which the page and the grader both read.

## One-time setup (repository owner)
1. **Publish the page:** Settings → Pages → *Source* → **GitHub Actions**. The *Publish the page* workflow deploys it after every change. The site appears at `https://<owner>.github.io/<repository>/`.
2. **Let the workflows save changes, and only them:** the forms and the grader push their changes to `main` with a deploy key, so `main` can require a pull request from everyone else.
   1. On your computer: `ssh-keygen -t ed25519 -N "" -C leaderboard-bot -f leaderboard-bot`.
   2. Settings → Deploy keys → **Add deploy key**: paste `leaderboard-bot.pub`, tick **Allow write access**.
   3. Settings → Secrets and variables → Actions → **New repository secret** `LEADERBOARD_DEPLOY_KEY`: paste `leaderboard-bot` (the private key). Then delete both files.
   4. Settings → Rules → Rulesets → **New branch ruleset** for the default branch: *Restrict deletions*, *Block force pushes*, *Require a pull request before merging* (and, if you like, *Require status checks to pass*: `fast` and `slow`, the two jobs of *Test the grader*), with **Deploy keys** in the bypass list → set *Enforcement* to **Active**.

   Pushes made with the deploy key also start *Publish the page*, which is how the page updates after every change.
3. **Give facilitators access:** Settings → Collaborators → add each facilitator with **Write** access. That is what lets them run the forms.
4. **Run it once:** Actions → *Grade submissions* → **Run workflow**. The first run builds every existing submission and takes 20 to 40 minutes. After that, it runs by itself and only grades new commits.

The page, `participants.csv` and the grading reasons are public: anyone with the link can see every name and score.

## Lessons
Each lesson is one entry in `lessons.json`:

```json
{ "key": "framework_upgrade", "label": "Framework upgrade", "repo": "AtulKumarSharma79/Frameworkupgrade", "check": "framework_upgrade" }
```

`key` becomes the CSV column, `label` is shown on the page, `repo` is where participants open pull requests. `check` sets how much is automated:

| `check` | An exercise is *Correct* when | Extra work |
|---|---|---|
| `none` | a facilitator marks it | none |
| `build` | the submission builds | none |
| `tests` | our tests pass against it | none if the exercise repository ships the tests to make pass: `python3 grader/leaderboard.py pin-tests <key>` copies them, as of its latest commit (or `pin-tests <key> <full commit id>`), into `grader/fixtures/<key>/` and records the commit as `tests_commit`. Otherwise put test files there yourself, mirroring the project's paths |
| a custom name | anything a script can check | a module `grader/checks/<name>.py` |

The current custom checks:
- **FizzBuzz:** the participant's tests must pass against the real `FizzBuzz` and catch 7 deliberately broken versions.
- **REST API:** starts the app and calls `GET`/`POST /api/employees`, including the `400` cases.
- **Framework upgrade:** checks for Spring Boot 3.5.x, no `javax.*` imports, the removed properties gone, and `commons-text` 1.10 or newer. The original tests must pass, and the API must behave as before.
- **Container image:** requires an approved, pinned `eclipse-temurin` 21/25 image, a multi-stage build with a JRE runtime, a non-root user and a `.dockerignore`. It then builds and runs the image and calls the API.

**Adding a lesson with Claude:** in this repository, ask Claude Code to *"add the lesson in owner/repo to the leaderboard"*. The `add-lesson` skill (`.claude/skills/add-lesson`) walks through choosing the level, writing and testing the check, and recording existing submissions. To add one by hand, add the entry to `lessons.json` with `"check": "none"`, then raise the level later.

## For maintainers
- **Code:** Python 3 standard library only, in `grader/`, plus `scoring.js` at the top:
  - `scoring.js`: the rules (points, status words, how the CSV is read) and the only scoring code. The page loads it. `grader/rules.py` reads its `RULES` block and reads the CSV exactly as the page does; a test runs both on tricky files to prove it.
  - `exercise_tests.py`: `pin-tests`, which copies an exercise repository's own tests at one commit into a lesson's test files. Pinning a commit means a later change to the exercise repository regrades nobody until someone pins again.
  - `lessons.py`: loads and checks `lessons.json`; gives each lesson its check, test files and a version (changing one lesson re-grades only that lesson). It owns where `lessons.json` and `grader/fixtures/` live, and is the only code that writes `lessons.json`.
  - `roster.py`: every change to `participants.csv`: facilitator actions, undo, and applying graded results (results only go up). It writes each value one way (`correct`, `submitted` or blank; counts as a number or blank), so hand edits in any spelling the page accepts are tidied on the next save.
  - `grade.py`: finds pull requests (GitHub, or an in-memory stand-in in tests) and grades the ones that need it.
  - `submissions.py`: `grader/results.json`, one entry per pull request: whether a result still counts, each person's best status, the early-PR bonus, per-lesson counts.
  - `executor.py`: the only way participant code runs: a clean environment, timeouts, clean-up, and the CI sandbox user. Also `fetch` (git) and `host_run` for trusted tools. The one exception is Docker: the container check builds and runs the participant's image on the machine's Docker daemon, outside the sandbox user.
  - `checks/`: one module per check (`build`, `tests`, and one per custom check), built from `checks/toolkit.py`: Gradle, the executor, and a `RunningApp` (a jar or a container). Editing a check's module regrades only the lessons that use it; editing the toolkit regrades them all.
  - `leaderboard.py`: the single command line, the same commands the forms run.
- **Tests:** `python3 -m unittest discover grader/tests` runs everything (a few minutes); `GRADER_FAST=1` skips the slow tier (Gradle builds, Docker, and `grader/tests/simulate_workflows.py`, which runs every workflow's shell steps against a scratch repository) and takes about 40 seconds. *Test the grader* runs the fast tier and everything as two jobs on every pull request, plus `ruff check` (settings in `pyproject.toml`). To lint and run the fast tier before each commit: `git config core.hooksPath .githooks`. The check tests need a JDK and network access, and the container test needs Docker; each skips itself without them.
- **Security:** pull-request code runs only in the grading job, which has a read-only token and no secrets. Within that job it runs as a separate `grader-sandbox` user that cannot write to the grader or its results, and everything it started is killed after each check. Saving results happens in a separate job, which refuses a malformed `results.json`, and pushes with the deploy key; no workflow has a token that can write. Tests enforce these rules, not just this paragraph: `test_boundaries.py` (where processes may start) and `test_workflows.py` (permissions, inputs never reaching a shell, actions pinned to commits). Run `leaderboard.py grade` locally only with `--no-run`, because without it the grader builds and runs code from the pull requests.
- **Walkthrough:** `walkthrough.py` serves this folder on 127.0.0.1 and opens `walkthrough/`, showing made-up example people (generated from `lessons.json`) unless run with `--real`. The words are in `walkthrough/steps.js`; it points at the leaderboard only through `data-tour="..."` attributes in `index.html`, and a test fails if one goes missing.
- **Preview locally:** run `python3 walkthrough.py` to see the page with made-up example people (or `--real` for the real scores); `python3 -m http.server 8000` serves the plain page.
- **After merging changes to a check:** the next grading run re-grades every submission whose lesson's version changed (its check, the shared grader code, or its test files).
- **Decisions:** `docs/adr/` records layout choices that were considered and kept, so they are not re-proposed.
