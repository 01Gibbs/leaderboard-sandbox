# Java Exercise Leaderboard

A public leaderboard for the workshop. Participants submit each exercise as a pull request; the leaderboard picks them up, grades them, and ranks everyone by points. Facilitators adjust scores from the facilitator page, with nothing to install.

**New here? Start with the walkthrough.** In this folder, run `python3 walkthrough.py` (Windows: `py walkthrough.py`; Python 3.8 or newer). It opens a five-minute guided tour of the leaderboard in your browser: what people see, how scores get there, the facilitator page, and what a workshop repo needs. It only runs on your computer; press Ctrl+C to stop.

- **Facilitators:** everything you need is in [FACILITATOR.md](FACILITATOR.md).
- **Project lead:** set it up once (below), then add lessons as the workshop grows.
- **Taking over, or moving it to a new home:** [docs/TAKEOVER.md](docs/TAKEOVER.md), with prompts for Claude Code.

## How it works

```
participant opens a PR ──► "Grade submissions" (daily, or Grade now) ──► participants.csv ──► public page
                                                                        ▲
facilitator page: pick a person, act, Send ──► one GitHub issue ────────┘
                  (or a form in the Actions tab)
```

1. **Submissions.** The *Grade submissions* workflow grades pull requests on each lesson's repository (listed in [`lessons.json`](lessons.json)). It runs once a day by itself, and straight away when a facilitator presses **Grade now** on the facilitator page (which opens the workflow on GitHub for them to press **Run workflow**). Nothing is needed in the exercise repositories, so lessons in repositories you do not own work too. Optionally, an exercise repository's owner can connect it with `grader/setup-pr-trigger.sh`, which adds a small workflow and a token there (see [`grader/exercise-repo/notify-leaderboard.yml`](grader/exercise-repo/notify-leaderboard.yml)): its pull requests are then graded within a minute of changing. Why this way: [docs/research/grading-without-exercise-repo-access.md](docs/research/grading-without-exercise-repo-access.md). The workflow lists the pull requests on each lesson's repository. Each author is a participant: anyone new gets a row, named from their GitHub profile, and the exercise shows as *Submitted*. Pull requests from the repository's owner, from bots, and ones closed without merging are not submissions (one closed after it was graded gives up its early-PR credit; the status it earned stays until a facilitator marks it lower).
2. **Grading.** Each pull request's latest commit is checked once, with the grader's own tests (so editing the tests in a pull request does not help). If it passes, the exercise shows as *Correct*. The reason for every pass or fail is kept in `grader/results.json`.
3. **Facilitator changes** (points, names, merges, undo) are made from the facilitator page (`facilitator.html`), which sends each as a filled-in GitHub issue that only collaborators' changes are made from, or from the same forms in the Actions tab. Each one logs the rows it changed, before and after, in `grader/history.json`, so undo can change back exactly the cells it touched. Changes made at the same moment all land: each run applies its change to the latest version and retries if someone else saved first.
4. **The page** (`index.html`, served by GitHub Pages) reads `participants.csv`, `lessons.json` and `dashboard.json` (title, workshops, next week's plan, kudos), and updates a minute or two after any change.

The grader never lowers a result, so a facilitator's changes are never overwritten by the next grading run.

## Points
Submitted **10**, correct **30**, each stretch credit **+5**, each time helping a colleague **+5**, plus any bonus points a facilitator gives. The first **3** pull requests on each exercise earn their authors a stretch credit each (the `pr_stretch` column, worked out by the grader on every run; don't edit it). Equal points share a rank; within it, people with more correct exercises are listed first. They live in one place, the `RULES` block at the top of `scoring.js`, which the page and the grader both read.

## Coming from the original leaderboard
This repository grew out of [AtulKumarSharma79/Leaderboard](https://github.com/AtulKumarSharma79/Leaderboard), where `participants.csv` was edited by hand. Each thing done there has a place here:

| There | Here |
|---|---|
| Run `sync_participants.py` to add pull request authors and early-PR bonuses | Automatic: the grader lists each exercise repository's pull requests (once a day, or on **Grade now**), adds each author, grades the work and works out `pr_stretch` |
| Mark a status `correct` by editing the CSV | The checks decide from the pull request itself. For an exercise without a check, a facilitator presses **Mark correct** on the facilitator page |
| Add `stretch` or `helped` by editing the CSV | **+1 help**, **+1 stretch** or **More → Bonus points** on the facilitator page (or edit the CSV: direct edits are kept, and undo leaves them alone) |
| Exercise names and points in `index.html` (`TRACKS`, `PTS`) | `lessons.json` (one entry per exercise) and the `RULES` block in `scoring.js` |
| Workshop dates, next week's plan and kudos in `dashboard.json` | The same file, unchanged |
| `start.bat`, or the file picker when `index.html` is opened from disk | `python3 walkthrough.py --real` (Windows: `py walkthrough.py --real`) serves the real files; `python3 -m http.server 8000` serves the plain page |

A status here comes from the grader's checks, so a hand edit that marks a failing pull request `correct` is not carried over: the reasons are in `grader/results.json`, and a new commit is graded again at the next grading run.

## One-time setup (repository owner)
**The quick way:** in a clone of the repository, run `grader/setup-leaderboard.sh` (needs the GitHub CLI, logged in as the owner). It does every step below with `gh`, asking before each one, skips what is already done, and finally offers to connect the exercise repositories (`grader/setup-pr-trigger.sh`), which is optional. The steps, if you prefer Settings:

1. **Publish the page:** Settings → Pages → *Source* → **GitHub Actions**. The *Publish the page* workflow deploys it after every change. The site appears at `https://<owner>.github.io/<repository>/`.
2. **Let the workflows save changes, and only them:** the forms and the grader push their changes to `main` with a deploy key, so `main` can require a pull request from everyone else.
   1. On your computer: `ssh-keygen -t ed25519 -N "" -C leaderboard-bot -f leaderboard-bot`.
   2. Settings → Deploy keys → **Add deploy key**: paste `leaderboard-bot.pub`, tick **Allow write access**.
   3. Settings → Secrets and variables → Actions → **New repository secret** `LEADERBOARD_DEPLOY_KEY`: paste `leaderboard-bot` (the private key). Then delete both files.
   4. Settings → Rules → Rulesets → **New branch ruleset** for the default branch: *Restrict deletions*, *Block force pushes*, *Require a pull request before merging* with **0** required approvals (GitHub never counts an author's own approval, so any higher number stops you merging your own pull requests), and *Require status checks to pass*: `fast` and `slow`, the two jobs of *Test the grader*, without *Require branches to be up to date* (the grader commits to main whenever a pull request changes). Add **Deploy keys** to the bypass list → set *Enforcement* to **Active**.

   Pushes made with the deploy key also start *Publish the page*, which is how the page updates after every change.
3. **Give facilitators access:** Settings → Collaborators → add each facilitator with **Write** access. Under Issues → Labels, add a `facilitator` label, which the facilitator page's issues are given. That is what lets them use the facilitator page and the forms.
4. **Run workflows for collaborators only:** Settings → Actions → General → *Approval for running fork pull request workflows from contributors* → **Require approval for all external contributors**. Then nobody outside the Collaborators list starts a workflow here: their pull requests wait for a collaborator to approve the run, and their issues change nothing (`changes-from-issues.yml` checks GitHub's author association, so the run that starts skips its jobs).
5. **Run it once:** Actions → *Grade submissions* → **Run workflow**. The first run builds every existing submission and takes 20 to 40 minutes. After that, it runs by itself and only grades new commits.
6. **Optional: connect the exercise repositories you own:** run `grader/setup-pr-trigger.sh` (you need admin access to them). It walks you through a token and adds a small workflow to each, so a pull request there is graded within a minute. Without it, pull requests are graded once a day, or when a facilitator presses **Grade now**.

The page, `participants.csv` and the grading reasons are public: anyone with the link can see every name and score.

## Lessons
Each lesson is one entry in `lessons.json`:

```json
{ "key": "framework_upgrade", "label": "Framework upgrade", "repo": "AtulKumarSharma79/Frameworkupgrade", "check": "framework_upgrade" }
```

`key` becomes the CSV column, `label` is shown on the page, `repo` is where participants open pull requests. The repository must be public: the grader reads it without a token. `check` sets how much is automated:

| `check` | An exercise is *Correct* when | Extra work |
|---|---|---|
| `none` | a facilitator marks it | none |
| `build` | the submission's Gradle project (with its `gradlew` wrapper) builds, on JDK 17, 21 or 25 | none |
| `tests` | our tests pass against it | none if the exercise repository ships the tests to make pass: `python3 grader/leaderboard.py pin-tests <key>` copies them, as of its latest commit (or `pin-tests <key> <full commit id>`), into `grader/fixtures/<key>/` and records the commit as `tests_commit`. Otherwise put test files there yourself, mirroring the project's paths |
| a custom name | anything a script can check | a module `grader/checks/<name>.py` |

The current custom checks:
- **FizzBuzz:** the participant's tests must pass against the real `FizzBuzz` and catch 7 deliberately broken versions.
- **REST API:** starts the app and calls `GET`/`POST /api/employees`, including the `400` cases.
- **Framework upgrade:** checks for Spring Boot 3.5.x, no `javax.*` imports, the removed properties gone, and `commons-text` 1.10 or newer. The original tests must pass, and the API must behave as before.
- **Container image:** requires an approved, pinned `eclipse-temurin` 21/25 image, a multi-stage build with a JRE runtime, a non-root user and a `.dockerignore`. It then builds and runs the image and calls the API.
- **Replace a library:** no Joda-Time, log4j 1.x or opencsv 2.3 in the source, `log4j.properties` deleted, none of the three in the built app (directly or through another library), and the starter's tests pass unchanged, so the API, CSV export and log message behave as before. The library audit and the Bruno comparison are left to facilitators.

**Adding a lesson without code** (the facilitator page's way, coming next; the command line today): `python3 grader/leaderboard.py add-lesson <key> "Label" <owner/repo> none|build|tests [tests-repo] [tests-folder]`, also allowed as a row in a facilitator batch. Only the generic levels, never a custom check. With `tests`, the tests are pinned from the exercise repository, or from another public repository and a folder in it: plain files only (a symbolic link or submodule is refused), at most 500 files and 5 MB. The lesson is saved as `"status": "checking"`, which nothing grades or shows until a trial proves its tests work. `remove-lesson <key>` removes one added by mistake; its results and its participants.csv column are kept (nothing shows them), so adding it again brings them back. A lesson with a custom check is added or removed through a pull request. Both are saved by the bot, like any facilitator change. Why this way: [docs/research/lessons-from-the-page.md](docs/research/lessons-from-the-page.md).

**Adding a lesson with Claude:** in this repository, ask Claude Code to *"add the lesson in owner/repo to the leaderboard"* (a fuller prompt is in [docs/TAKEOVER.md](docs/TAKEOVER.md)). The `add-lesson` skill (`.claude/skills/add-lesson`) walks through choosing the level, writing the check and proving it with tests. **By hand:** add the entry to `lessons.json` with `"check": "none"` in a pull request; once it is merged, run *Grade submissions* (or press **Grade now**) and the existing pull requests show as *Submitted*. Raise the level later.

## For maintainers
- **Code:** Python 3 standard library only, in `grader/`, plus `scoring.js` at the top:
  - `scoring.js`: the rules (points, status words, how the CSV is read) and the only scoring code. The page loads it. `grader/rules.py` reads its `RULES` block and reads the CSV exactly as the page does; a test runs both on tricky files to prove it.
  - `lesson_changes.py`: `add-lesson` and `remove-lesson`, the facilitator page's way (generic levels only, saved as checking).
  - `exercise_tests.py`: `pin-tests`, which copies an exercise repository's own tests (or another public repository's) at one commit into a lesson's test files, as plain files only and within a size cap. Pinning a commit means a later change to the exercise repository regrades nobody until someone pins again.
  - `lessons.py`: loads and checks `lessons.json`; gives each lesson its check, test files and a version (changing one lesson re-grades only that lesson). It owns where `lessons.json` and `grader/fixtures/` live, and is the only code that writes `lessons.json`.
  - `roster.py`: every change to `participants.csv`: facilitator actions, undo, and applying graded results (results only go up). It writes each value one way (`correct`, `submitted` or blank; counts as a number or blank), so hand edits in any spelling the page accepts are tidied on the next save.
  - `grade.py`: finds pull requests (GitHub, or an in-memory stand-in in tests) and grades the ones that need it.
  - `submissions.py`: `grader/results.json`, one entry per pull request: whether a result still counts, each person's best status, the early-PR bonus, per-lesson counts.
  - `executor.py`: the only way participant code runs: a clean environment, timeouts, clean-up, and the CI sandbox user. Also `fetch` (git) and `host_run` for trusted tools. The one exception is Docker: the container check builds and runs the participant's image on the machine's Docker daemon, outside the sandbox user.
  - `checks/`: one module per check (`build`, `tests`, and one per custom check), built from `checks/toolkit.py`: Gradle, the executor, and a `RunningApp` (a jar or a container). Editing a check's module regrades only the lessons that use it; editing the toolkit regrades them all.
  - `leaderboard.py`: the single command line, the same commands the forms run.
- **Tests:** `python3 -m unittest discover grader/tests` runs everything (a few minutes); `GRADER_FAST=1` skips the slow tier (Gradle builds, Docker, and `grader/tests/simulate_workflows.py`, which runs every workflow's shell steps against a scratch repository) and takes about 40 seconds. *Test the grader* runs the fast tier and everything as two jobs on every pull request, plus `ruff check` (settings in `pyproject.toml`). To lint and run the fast tier before a commit: `git -c core.hooksPath=.githooks commit`. The check tests need a JDK and network access, and the container test needs Docker; on your computer each skips itself without them, while on GitHub Actions a starter that cannot be cloned fails the run. `EveryCheckIsTestedTests` fails while a check module has no test. The facilitator page's browser journeys need Playwright (`grader/tests/test_facilitator_browser.py` says how), and `grader/tests/e2e_github.py` runs every real workflow on a sandbox copy on GitHub and undoes what it changed.
- **Security:** pull-request code runs only in the grading job, which has a read-only token and no secrets. Within that job it runs as a separate `grader-sandbox` user that cannot write to the grader or its results, and everything it started is killed after each check. Saving results happens in a separate job, which refuses a malformed `results.json`, and pushes with the deploy key: no workflow's token can write to the repository, and only *Publish the page* can deploy the page. Tests enforce these rules, not just this paragraph: `test_boundaries.py` (where processes may start) and `test_workflows.py` (permissions, inputs never reaching a shell, only the deploy key passed to the forms, actions pinned to commits). Run `leaderboard.py grade` locally only with `--no-run`, because without it the grader builds and runs code from the pull requests.
- **Facilitator page:** `facilitator.html` (published with the leaderboard) is person-first: pick a person, act, and each change waits in a Changes box. Send opens `.github/ISSUE_TEMPLATE/facilitator-changes.yml` filled in with every waiting change (one per line), which `leaderboard.py batch` applies, recording each row's outcome in `grader/batches.json` and each change in `grader/history.json` with an id, so `undo <id>` reverses any one. The page follows what was sent by reading those two files without a token. Every read and poll it makes goes through `github-reader.js`: conditional requests; one budget of 50 reads an hour per open page, with its polls (waiting changes, Grade now) spaced so that together they stay within it; slowing down after errors; and, when GitHub says its limit is reached, waiting until GitHub's reset and telling the facilitator whose limit it is. GitHub allows 60 reads an hour without a token per network, counting unchanged answers, so two facilitators' pages open on one network can still reach it; the page then waits it out rather than giving up (`grader/tests/test_github_reader.py` runs it in Node with a stand-in clock). Each Actions-tab form (listed in `grader/issue_form.py`'s `FORMS`) also has its own issue template (`.github/ISSUE_TEMPLATE/facilitator-*.yml`, under *New issue* on GitHub); `changes-from-issues.yml` checks the author's permission on the repository (`grader/issue_form.py`: write, maintain or admin), runs the same command as the Actions form, answers the issue, closes it and locks it. No tokens: the Collaborators list decides. `test_issue_form.py` fails if a template, the parser and the workflows disagree. `facilitator_walkthrough.py` serves it on a throwaway practice copy, with a stand-in for GitHub that applies each issue at once and answers it as the workflow would (`issue_form.answer`). `grader/tests/test_facilitator_page.py` and `test_facilitator_browser.py` test the page and the practice copy.
- **Walkthrough:** `walkthrough.py` serves this folder on 127.0.0.1 and opens `walkthrough/`, showing made-up example people (generated from `lessons.json`) unless run with `--real`. The words are in `walkthrough/steps.js`; it points at the leaderboard only through `data-tour="..."` attributes in `index.html`, and a test fails if one goes missing.
- **Preview locally:** run `python3 walkthrough.py` to see the page with made-up example people (or `--real` for the real scores); `python3 -m http.server 8000` serves the plain page.
- **After merging changes to a check:** the next grading run re-grades every submission whose lesson's version changed (its check, the shared grader code, or its test files).
- **Decisions:** `docs/adr/` records layout choices that were considered and kept, so they are not re-proposed.
