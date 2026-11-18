# Adding a lesson from the facilitator page

*Research note, 17 November 2026. Audience: project lead.*

> **Status (17 Nov 2026).** Slice 1 (the commands, hardened pinning, the bot's save) and the trial that puts a lesson live are built. The page form, the live e2e journey and the JUnit check are next.
>
> **Decisions (17 Nov 2026, project lead).**
> - **Saving:** straight to main with the bot's deploy key (option a), behind guard checks, so a lesson is proved to work before it is used. A new lesson is saved as *checking* and hidden from the board. A trial in the grading job builds its starter with the pinned tests (they must compile; failing is expected), and, when a public solution repository is given, the solution must pass them. Only then does the lesson go live (its column appears and its pull requests are graded). A failed trial says why on the issue and the page, and the lesson stays hidden.
> - **Tests:** public repositories only. A private solutions repository can be made public before the solution session, and the lesson's tests re-pinned from it then.
> - **Where:** on the facilitator page only, not as an Actions-tab form.
> - **Pinning caps:** regular files only (no symlinks or submodules), at most 500 files and 5 MB, as suggested below.
> - **Live test repositories:** `01Gibbs/leaderboard-sandbox-exercise` (Greeting, used by the e2e) and `01Gibbs/leaderboard-sandbox-exercise-2` (Roman numerals, for the team demo), both public, each a Gradle project whose tests compile against the starter and fail until solved.


This note designs the journey the lead asked for. A facilitator fills in a form on the facilitator page, the lesson lands in `lessons.json`, and the board grows a column. It builds on four earlier notes and does not repeat them:

- [`lessons-by-workflow.md`](lessons-by-workflow.md) is the first design of an "Add a lesson" form. It was not built. This note re-checks its four blockers against today's code.
- [`adding-lessons.md`](adding-lessons.md) explains why tests are pinned from the exercise repository.
- [`grading-without-exercise-repo-access.md`](grading-without-exercise-repo-access.md) explains grading. It runs daily or on **Grade now**, and exercise repositories need nothing set up. They must be public.
- [`facilitator-batching.md`](facilitator-batching.md) covers how the page sends changes: one prefilled issue per Send, collaborators only, and no tokens on the page.

## Recommendation

**Make "add a lesson" one more row type in the batch the page already sends. Save it with the bot's existing deploy key, limited to `lessons.json` and `grader/fixtures/<key>/`. Start grading from a `push` trigger on those paths.** Nothing new is set up by the owner: no secret, no setting and no change to the ruleset.

```
facilitator.html  "Add an exercise" form
   │  pre-checks with ≤ 3 unauthenticated GitHub reads (repo public? gradlew? src/test? key free?)
   │  queues the row  ["add-lesson", repo, key, label, level, tests_repo, tests_dir, tests_commit]
   ▼  Send → prefilled "Facilitator: Changes" issue → facilitator presses Submit   (unchanged)
changes-from-issues.yml
   read    collaborator with write?  (unchanged, issue_form.py)
   change  facilitator-action.yml → run_and_push.sh → leaderboard.py batch
             add-lesson: validate → git fetch (anonymous, so a private repo fails) → copy regular files under src/test
             → write lessons.json entry + grader/fixtures/<key>/ → add the CSV column
           run_and_push.sh stages lessons.json + grader/fixtures/ as well → push with the deploy key
   answer  comment, close, lock  (unchanged)
   ▼  the deploy-key push starts, as today:
pages.yml        republishes lessons.json → index.html shows the new column
grade.yml        NEW trigger: push to main touching lessons.json or grader/fixtures/** → first grading run
test.yml         already runs on pushes that touch lessons.json or grader/** (after the fact, not a gate)
   ▲
facilitator.html follows grader/batches.json (unchanged); on success also re-reads lessons.json
```

**The form's fields:**

| Field | Required | Notes |
|---|---|---|
| Exercise repository | yes | `owner/name` or a pasted GitHub URL. Must be public. |
| Name shown | yes | The `label`. |
| Column key | derived | Made from the name (lowercase, `_`). Shown and editable. Must match `lessons.load`'s rule and not be taken or reserved [5]. |
| How it is graded | yes | `tests`, `build` or `none` only. The page offers only what its pre-checks allow. **No custom checks, ever.** |
| Where the tests are | if `tests` | "In the exercise repository" (default) or "Somewhere else". |
| Tests repository | if elsewhere | A public `owner/name`. A pasted `github.com/o/r/tree/<ref>/<folder>` URL fills all three fields. |
| Folder | optional | The Gradle project folder in the tests repository whose `src/test` is copied. Blank means the shallowest Gradle project, as today [7]. |
| Commit | optional | Blank means the latest commit on the default branch. The full commit id actually used is recorded. |

**Saving: option (a), extend the bot's save.** It is the only option with no extra step for anyone. The reasoning is in [Saving](#saving-which-option-and-why).

## How the pieces work today, and what changes

### What the page can check without a token

The page already reads GitHub's API without a token, with conditional requests [15]. Unauthenticated requests are allowed "if you are only fetching public data" and are limited to "60 requests per hour", counted per IP address [30]. The venue shares one IP, so the form must stay frugal. Three reads are enough:

1. `GET /repos/{repo}` gives `private`, `archived` and `default_branch`. A 404 means "not found, or private". The page says both.
2. `GET /repos/{repo}/git/trees/{default_branch}?recursive=1` returns the whole file list in one call. From it the page sees `gradlew`, whether `src/test/` exists, the number of test files and their sizes. The limit is "100,000 entries with a maximum size of 7 MB" [29]. A `truncated` answer is treated as "too big". Use this instead of the contents API, which stops at "1,000 files for a directory" [28].
3. The same call for the tests repository, only when the tests live elsewhere.

"Key not taken" needs no call, because the page already has `lessons.json` [15]. If GitHub answers 403 or 429 (rate limit), the page says "could not check now" and still lets the facilitator send. The server repeats every check.

What each check decides:

| Found | Levels offered |
|---|---|
| no `gradlew` (Node, Docker only, docs) | `none` only, saying why. `build` and `tests` need the wrapper [6]. |
| `gradlew`, no `src/test` anywhere | `build` or `none`, or `tests` from elsewhere |
| `gradlew` and `src/test` | `tests` (default), `build` or `none` |

### What the server does (`leaderboard.py add-lesson`)

A new command, next to `pin-tests` [8]. It is added to `BATCHABLE` [8] so a batch row can carry it.

1. **Validate.** Apply `lessons.load`'s rules to the new entry [5]. The level must be one of `none`, `build` or `tests`. Refuse a repository already used by another lesson (see [Edge cases](#edge-cases)). The folder must be a relative path without `..`.
2. **Fetch anonymously.** `executor.fetch` runs `git fetch` with no credentials [24]. A private or missing repository therefore fails, and the row is refused with "not found, or not public". No API token is needed.
3. **Copy, never run.** This job holds the deploy key, so it only copies files and runs nothing from the repository. `pin` already behaves this way [7]. Two hardening changes are needed (see [Security](#security-what-a-collaborator-could-then-do)): copy regular files only, and cap the size.
4. **Write.** Add the `lessons.json` entry, the fixtures (through `pin`), and `tests_repo` and `tests_dir` when the tests came from elsewhere. Then save the roster once, so the CSV column exists at once. `_Sheet` adds any missing lesson column whenever it writes [16].
5. **Report.** The row's message is "Added *Label* (tests: 7 files from o/r at abc1234)". When the level is `none`, it adds "a facilitator marks it". `batches.json` carries this back to the page, which already shows each row as Done or Not done [15].

### After saving

- **The page and the board.** `pages.yml` copies `lessons.json` and republishes on every deploy-key push [13]. `index.html` reads `lessons.json` for its columns [17]. The facilitator page loads `lessons.json` once (`if (!lessons.length)`, `facilitator.html:285`) [15]. It must re-read it from the API when a batch lands, or the new exercise will not appear on the facilitator page until a reload.
- **First grading.** Add `push: branches: [main], paths: [lessons.json, 'grader/fixtures/**']` to `grade.yml` [12]. The bot's pushes use the deploy key, not `GITHUB_TOKEN`, so they start workflows. `pages.yml` already relies on this [13]. Grading's own saves touch only `participants.csv` and `grader/*.json`, so they never start it again. This beats dispatching from the job. `GITHUB_TOKEN` *can* start `workflow_dispatch` [26], but that would need `actions: write` on a job. The trigger also grades lessons added by pull request straight away, which today needs a manual run (skill step 6) [20]. `grade.yml` queues runs and cancels none [12].
- **Walkthrough.** `facilitator_walkthrough.py` serves a stand-in GitHub API to the page in practice mode [22]. It needs fake answers for `GET /repos/...` and `.../git/trees/...` pointing at a local example repository, so the form can be practised.
- **FACILITATOR.md.** Add a short "Add an exercise" section: fields, the three levels, "tests must be public", and how to remove one.

## How "tests located elsewhere" works

`exercise_tests.pin` already takes a `url` [7]. Tests use it to pin from a local folder [23]. Three things are missing:

1. **The command line does not expose it.** `pin-tests` calls `pin(root, lesson, commit)` [8].
2. **Nothing records where the tests came from.** `lessons.json` allows only `key`, `label`, `repo`, `check` and `tests_commit` [5]. A later re-pin would silently take tests from the exercise repository. Add `tests_repo` (`owner/name`) and `tests_dir`. Validate both in `load`. `pin` uses them when they are present.
3. **No way to pick a folder.** `pin` copies every `src/test` under the shallowest Gradle project [7]. A solutions repository often holds several projects (`step1/`, `step2/`). `tests_dir` names the one to use.

Paths are kept relative to the tests repository's Gradle project [7]. They are copied over the submission's Gradle project [6]. If the two layouts differ (`app/src/test` in one, `src/test` in the other), the tests land in the wrong place. The page compares the two trees and warns when the test folders' parents do not exist in the exercise repository.

**Raw URL: no.** One raw file loses its package path. A raw URL also makes the job fetch from any host. Accept GitHub repositories only.

**Version.** `Lesson.version` hashes the test files' paths and contents [5]. The new fields only decide *which* files are copied, so they need not enter the version. A re-pin from elsewhere that changes the files regrades everyone. One that changes nothing regrades no one.

### Tests in a private solutions repository

**The tests become public anyway.** Pinned tests are committed into `grader/fixtures/` of the leaderboard. That repository is public: the page reads it without a token [15]. Any private test that is pinned is therefore published. So the first question is whether the tests really need to be secret.

| Option | Secret stays secret? | Owner overhead | Verdict |
|---|---|---|---|
| Make the tests repository public, or copy the tests into a public one | no | none | **Recommended** |
| Fine-grained token, read-only Contents on that one repository, stored as a secret and used only by `add-lesson` | no: still committed to `fixtures/` | Atul creates the token and secret for each new repository. Tokens can be limited to "only select repositories". They expire unless no-expiry is allowed, and they stop working if the creator loses access [35]. | No |
| Read-only deploy key on the solutions repository | no | One key pair per repository: "You can't reuse a deploy key for multiple repositories" [31]. Plus one more secret each time. | No |
| Workflow `GITHUB_TOKEN` | — | — | Impossible: "limited to the repository that contains your workflow" [26]. `actions/checkout` says a different private repository needs your own token [27]. |
| Fetch private tests at grading time, never commit them | yes | A secret in the `grade` job, which runs participant code. A test forbids this [3]. | **Rejected**: participant code could read the secret |

Recommendation: **public only.** The form says so, and the server refuses a repository it cannot fetch anonymously. Hidden tests would need their own design, with a separate grading job that holds no participant code. That is out of scope.

## Saving: which option, and why

Today only four state files are staged [2], and a test pins that list [3]. `main` takes everything else only through a pull request. The deploy key is the ruleset's bypass actor (`"actor_type": "DeployKey", "bypass_mode": "always"`) [18]. GitHub's docs list the actors that may bypass a ruleset [32]. They describe a "For pull requests only" bypass as one that does not allow direct pushes, which implies a full bypass does [32].

| | (a) Extend the bot's save | (b) The workflow opens a pull request | (c) Keep lessons outside `main` (a data branch) |
|---|---|---|---|
| Steps for facilitator | Submit (as today) | Submit, then someone merges | Submit |
| Owner setup | none | Turn on "Allow GitHub Actions to create and approve pull requests", which is off by default in personal accounts [33] | Pages and the grader read two branches |
| CI before landing | no (after the fact [14]) | A PR opened with `GITHUB_TOKEN` runs workflows only after approval [26]. Otherwise it needs a personal token or app: more owner overhead | no |
| Time to board | about 2 minutes | minutes to days (someone must merge) | about 2 minutes |
| Code paths | one: the existing save | new: branch, PR, merge, polling | new everywhere |

**Choose (a).** It reuses the save every facilitator change already uses. It gives no one more power than they have today, as the next section shows.

### Security: what a collaborator could then do

- **Nothing more over code than today.** A write collaborator can already merge their own pull request. The ruleset requires **0** approvals plus the `fast` and `slow` checks [18]. The form adds no new authority. It adds a quicker path for one narrow kind of data.
- **The narrow kind.** The command, not the issue, decides what is written. The `check` field takes only `none`, `build` or `tests`. Custom checks are Python modules under `grader/checks/` [19], and the command never writes there. `run_and_push.sh` stages named paths after a hard reset to `origin/main` [2], so nothing else can ride along. Keep a test like [3] that pins the staged list exactly: the four state files, plus `lessons.json` and `grader/fixtures/`.
- **What pinned tests can do.** They are Java and run only in the `grade` job. That job has `contents: read`, no secrets [3][12], and runs as a separate sandbox user, the same as every participant's code. The `fast` and `slow` jobs also run on the push [14] and will show if a test file broke the suite.
- **New risk to close: symlinks.** `pin` uses `shutil.copytree`, which by default copies the *target* of a symlink [7]. The job that copies holds the deploy key: `actions/checkout` configures it in git, and "the post-job step removes the SSH key", so it is on disk while the job runs [27]. A hostile tests repository could add a symlink under `src/test` pointing into the runner's temporary folder, and the key would be committed to a public repository. Before the form ships, `pin` must copy **regular files only**, refuse symlinks and submodules, and stay under the `src/test` folder. Add a test with a symlink in it.
- **New risk to close: size.** Cap the pin at about 500 files and 5 MB (both numbers to agree). Refuse beyond that with a reason.
- **Who.** Only write, maintain or admin collaborators get a run [9][10]. That is unchanged.

## Edge cases

| Case | Handling |
|---|---|
| Key already used, or reserved | The page blocks it, and `lessons.load` refuses it on the server [5]. |
| Same repository already a lesson | **Refused** for now. Results are keyed `owner/repo#N` without the lesson [4], so two lessons would overwrite each other. Add the same rule to `lessons.load`, which does not check this today [5]. |
| Two lessons on one repository (sections) | Later slice: key results by lesson as well, with a one-off migration of `results.json` (lessons-by-workflow §2 [1]). |
| Two adds at once | `run_and_push.sh` reruns the command on the newest `main` when a push loses the race [2]. The second add with the same key is then refused with a reason. Different keys both land. |
| Private or missing repository | The anonymous fetch fails. The row says "not found, or not public". |
| Renamed repository | `git fetch` keeps working through GitHub's redirect [34]. The API redirect is not stated there [34]. The grader skips an unreachable repository for that run [25]. Fix: edit `repo` (see below). Results move to the new key on the next run, because results are keyed by repository [4]. A new repository created with the old name breaks the redirect [34]. |
| Tests do not compile against the starter | They cannot be built in the saving job (deploy key). They show up as failed results with Gradle's message on the first grading. Optional slice 5: the `grade` job also grades the starter once per lesson version and reports "tests compile, N fail" on the page. |
| Huge test folder | Refused over the cap. The page warns first, using the tree's sizes. |
| Not a Gradle project | Only `none` is offered. The server refuses `build` or `tests` because `gradle_project` finds nothing [7]. |
| Rate limit on the page | The page says it could not check and still lets the row be sent. The server re-checks with anonymous `git`, which uses no API call. |
| Archived repository | Warn and allow. Participants cannot open pull requests, so the column will stay empty. |
| Lesson added by mistake | `remove-lesson <key>`, below. |

### Removing and editing

- **`remove-lesson <key>`** is batchable and offered on the page next to each lesson. It refuses lessons with custom checks, which stay a pull-request job like any code. It removes the entry and `grader/fixtures/<key>/`. The CSV column stays: `_Sheet` keeps columns it does not know [16], and the board shows only lessons in `lessons.json` [17]. Graded results stay in `results.json` and are ignored. Re-adding the same key therefore brings back marks and results. The test must prove all three. `undo` stays for roster changes only [8]. Undo on an add row sends `remove-lesson` instead.
- **`edit-lesson <key> label|repo <value>`** changes the name shown or follows a renamed repository.
- **Re-pin:** `pin-tests <key> [commit]` becomes batchable. It already refuses custom checks [7], and it now uses `tests_repo` and `tests_dir`. A re-pin regrades everyone whose tests changed, through the version [5].

## The four blockers from `lessons-by-workflow.md`

| Blocker [1] | Today | Removed by |
|---|---|---|
| A workflow-added lesson would not be saved: the save stages only state files | **Stands.** Four files staged [2], pinned by a test [3]. | Slice 1: stage `lessons.json` and `grader/fixtures/`, and update the test. |
| Two lessons on one repository share results | **Stands.** `key()` is `repo#N` [4], and `load` allows two lessons on one repository [5]. | Refuse duplicate repositories now. Re-keying is a later slice. |
| Lesson settings are not in its version | **Does not bite this design.** The version covers the check, its module, shared code and the test files [5]. There are no other settings yet. The new `tests_repo` and `tests_dir` change only which files are copied, and the files are hashed. | Nothing now. Any future field that changes how grading runs (filters, tags) must enter the version. |
| Tests can be switched off in `build.gradle` | **Stands.** `tests` trusts Gradle's exit code [6]. A participant can disable the `test` task and pass. | Slice 4: after `gradle test`, read `build/test-results/**/*.xml` and require every pinned test class to have run and passed. Every form-added lesson uses `tests`, so this matters more once the form exists. |

## Build plan

Each slice ships on its own, through a pull request, with its evidence.

1. **Add from the command line, saved by the bot.** `add-lesson` and `remove-lesson` in `leaderboard.py`, both in `BATCHABLE`. `pin` copies regular files only, has a size cap, and takes `tests_repo` and `tests_dir`, which become new fields in `lessons.json`. `run_and_push.sh` stages `lessons.json` and `grader/fixtures/`. The `grade.yml` push trigger.
   *Evidence:* unit tests in `test_exercise_tests.py` and `test_lessons.py` (symlink refused, cap, other repo and folder, duplicate repository refused, remove then re-add restores marks). `test_workflows.py` pins the new staged list and the grade trigger paths. `simulate_workflows.py` runs a `Facilitator: Changes` issue with an `add-lesson` row against a local origin, then checks the commit contains only `lessons.json`, the fixtures and the state files.
2. **The form on the page, in practice mode.** The "Add an exercise" form, its pre-checks, the row in the Changes box, re-reading `lessons.json` when the batch lands, and remove. Fake tree and repository answers in `facilitator_walkthrough.py`.
   *Evidence:* `test_facilitator_page.py` (field derivation, offered levels per tree, rate-limit fallback). `test_facilitator_browser.py` journey on the practice server: add → Done → the column appears → remove → it is gone.
3. **Live on the sandbox.** An `--add-lesson` journey in `e2e_github.py` against `01Gibbs/leaderboard-sandbox`. It sends an add row by issue, checks `lessons.json` and the fixtures on `main`, sees a `grade.yml` run started by `push` succeed, then sends `remove-lesson` and checks `main`'s `lessons.json` and `grader/fixtures/` match the start. Cleanup reuses `clean_up` [21]: it deletes its issues and its facilitator, issue and Pages runs. The grading run stays, as now. FACILITATOR.md section.
   *Evidence:* the e2e run's report, with "Left no trace".
4. **Tests cannot be switched off.** The JUnit XML check in `checks/tests.py`.
   *Evidence:* `test_checks.py` adds a submission that disables `test` in `build.gradle` and must fail with that reason, plus a passing one.
5. **(Optional) Starter check.** The grade job grades each lesson's default branch once per version and records it. The page shows "tests compile against the starter".
   *Evidence:* a `test_grading.py` case with a starter whose tests do not compile.

## Open questions for the lead

1. **Unreviewed lessons on `main`.** Option (a) lets any write collaborator add a lesson (data plus Java tests) without review. This note argues it adds no new power, given 0 required approvals. Is that acceptable, or do you want (b) with a merge step?
2. **Private tests.** Is "tests must be public, because they are committed to a public repository" acceptable? If hidden tests are needed, that is a separate design.
3. **Caps.** Agree the file and size limits for a pin (suggested: 500 files, 5 MB).
4. **The Actions-tab fallback.** ADR 0002 keeps one form per action [19]. Should `add-lesson` also get its own `facilitator-add-lesson.yml` form, or only the page?
5. **Which public exercise repository should the e2e use?** It needs a tiny Gradle project with `src/test`. For example a new public `01Gibbs/leaderboard-sandbox-exercise`.
6. **Slice 5.** Is it worth building, or are failing first results a good enough signal?

## Sources

Repository (this worktree, branched from `main` at 4d578b7):

1. `docs/research/lessons-by-workflow.md:5` (status, four blockers), `:42-44` (gaps), `:121` (deploy-key risk), §2 `:158-161` (shared-repo fixes)
2. `grader/run_and_push.sh:16-42` (reset, rerun on conflict), `:27` (staged files)
3. `grader/tests/test_workflows.py:21-27` (staged list pinned), `:52-72` (grade job read-only, no secrets; saves via deploy key)
4. `grader/submissions.py:51-53` (`key`: `repo#N`), `:125-129` (`keep_only`)
5. `grader/lessons.py:23` (FIELDS), `:48-63` (version), `:87-111` (`load`), `:114-123` (`record_pinned`)
6. `grader/checks/tests.py:6-10`; `grader/checks/toolkit.py:57-61, 87-112` (gradlew required, overlay)
7. `grader/exercise_tests.py:19` (GENERIC), `:26-59` (`pin`, `url`, `copytree`), `:62-69` (test folders)
8. `grader/leaderboard.py:31` (BATCHABLE), `:99-102` (`pin-tests` without `url`), `:129-166` (`run_batch`)
9. `grader/issue_form.py:25-37` (FORMS, batch), `:96-108` (permission check)
10. `.github/workflows/changes-from-issues.yml:20-86`
11. `.github/workflows/facilitator-action.yml:27-61`
12. `.github/workflows/grade.yml:12-26` (triggers, queue), `:32-57` (grade job)
13. `.github/workflows/pages.yml:1-9, 35` (deploy-key pushes start it; copies `lessons.json`)
14. `.github/workflows/test.yml:7-10` (push paths include `lessons.json`, `grader/**`)
15. `facilitator.html:176, 205-216` (unauthenticated reads), `:282-286` (loads lessons once), `:547-578` (Send), `:595-623` (follow)
16. `grader/roster.py:62-70` (`_Sheet` adds missing columns, keeps others), `:154-158`
17. `index.html:252, 428` (reads `lessons.json`)
18. `README.md:52` (ruleset, 0 approvals); `grader/setup-leaderboard.sh:261` (`DeployKey` bypass)
19. `docs/adr/0001-one-module-per-check.md`; `docs/adr/0002-one-workflow-per-facilitator-form.md`
20. `.claude/skills/add-lesson/SKILL.md` (steps 4, 6); `docs/TAKEOVER.md:9`
21. `grader/tests/e2e_github.py:1-15, 117-128` (journeys, `clean_up`)
22. `grader/tests/simulate_workflows.py:1-3`; `facilitator_walkthrough.py:1-8, 118-170`
23. `grader/tests/test_exercise_tests.py:68-69` (`pin` with a local `url`)
24. `grader/executor.py:65-72` (`fetch`: anonymous `git fetch`)
25. `grader/grade.py:92-102` (unreachable repository skipped for that run)

GitHub documentation (read 17 Nov 2026):

26. `GITHUB_TOKEN` (scope "limited to the repository that contains your workflow"; its events create no runs except `workflow_dispatch` and `repository_dispatch`; `pull_request` runs need approval): https://docs.github.com/en/actions/concepts/security/github_token
27. `actions/checkout` README (`ssh-key` configured in git config, "The post-job step removes the SSH key"; another private repository needs your own token): https://github.com/actions/checkout/blob/main/README.md
28. Get repository content (1,000 files per directory): https://docs.github.com/en/rest/repos/contents#get-repository-content
29. Get a tree (recursive: 100,000 entries, 7 MB): https://docs.github.com/en/rest/git/trees#get-a-tree
30. Rate limits for the REST API (60 per hour unauthenticated, per IP; public data only; `GITHUB_TOKEN` 1,000 per hour): https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
31. Managing deploy keys (single repository; read-only by default; no reuse across repositories): https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys
32. Creating rulesets for a repository (bypass actors; "For pull requests only"): https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository
33. Managing GitHub Actions settings for a repository ("Allow GitHub Actions to create and approve pull requests", off by default in personal accounts): https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository
34. Renaming a repository (git operations redirected; reusing the old name breaks redirects): https://docs.github.com/en/repositories/creating-and-managing-repositories/renaming-a-repository
35. Managing your personal access tokens (fine-grained: select repositories, expiry, tied to the creator): https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
