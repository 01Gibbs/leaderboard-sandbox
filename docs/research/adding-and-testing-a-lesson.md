# Adding a lesson, testing it, and how the workflows fit together

*Research note, 16 November 2026. Audience: project lead and facilitators.*

> **Status (16 Nov 2026).** Gaps 1 to 8, 10, 11 and 13 are addressed. README.md, the add-lesson skill and [docs/TAKEOVER.md](../TAKEOVER.md) now cover them. On GitHub Actions a starter that cannot be cloned fails the run, and `EveryCheckIsTestedTests` fails while a check has no test. Since this note, connecting exercise repositories is optional: grading runs daily or on **Grade now**, so gap 10 no longer applies. Gap 9 is noted in TAKEOVER.md. Gap 12 (custom roles) only matters in an organisation and is left as it is. Gap 14: the two older notes' status lines say what has moved.

This note is for someone who did not build the leaderboard, such as Atul hosting his own copy. It answers three questions from the code as it is on `main`. It builds on two earlier notes and does not repeat them:

- [`adding-lessons.md`](adding-lessons.md) explains why tests are pinned from the exercise repository, and why GitHub Classroom is not an option.
- [`lessons-by-workflow.md`](lessons-by-workflow.md) designs a "Facilitator: Add a lesson" form. That form is **not built**. Today a lesson is added through a pull request.

## Short answers

**1. How do I add a new lesson?** Add one entry to `lessons.json` with `key`, `label`, `repo` and `check` [1][2]. Then choose how "correct" is decided:

- `none`: a facilitator marks it.
- `build`: the Gradle build passes.
- `tests`: our copy of the tests passes. `pin-tests` copies them from the exercise repository [8].
- a custom name: a new module, `grader/checks/<name>.py` [4].

Merge the change through a pull request, because `main` takes no direct pushes [24]. Then run *Grade submissions* once (since this note, connecting the exercise repository with `grader/setup-pr-trigger.sh` [23] is optional). The quickest route is to ask Claude Code to *"add the lesson in owner/repo to the leaderboard"*. The `add-lesson` skill walks through every step [37].

**2. How do I test it?**

- For **every** lesson, `python3 -m unittest discover grader/tests -p test_lessons.py` checks `lessons.json` [35].
- For `build`, `tests` and custom lessons, add at least one passing and one failing submission to `grader/tests/test_checks.py`. Use its `run_check` helper, which grades a local folder exactly as a real pull request is graded [31].
- These are slow tests. They need a JDK and network access, and they are skipped under `GRADER_FAST=1` [32]. Run the full suite locally. The required `slow` job in *Test the grader* runs them on your pull request [33].
- A `none` lesson needs no check tests.

**3. How does the workflow work?**

- **Participant path.** A pull request on the exercise repository starts a small workflow there. That workflow sends a `repository_dispatch` event to the leaderboard [22]. *Grade submissions* then grades every new commit in a read-only, sandboxed job [18]. A second job saves the results to `main` with a deploy key [19][20]. That push starts *Publish the page*, which deploys to GitHub Pages [21].
- **Facilitator path.** The facilitator page opens a pre-filled GitHub issue [29]. `changes-from-issues.yml` checks that the author has write access, then runs `leaderboard.py batch` through the shared `facilitator-action.yml`. It pushes with the same deploy key, and then answers, closes and locks the issue [25][26][10]. The push publishes the page again.

---

## 1. Adding a lesson, in detail

### What a lesson is

A lesson is one object in `lessons.json` [1]. `lessons.load` accepts only the fields `key`, `label`, `repo`, `check` and `tests_commit` [2]. It reports every problem at once:

- `key` must match `[a-z][a-z0-9_]*`. It must not repeat another key or a reserved CSV column.
- `repo` must look like `owner/name`.
- `check` must be `none` or the name of a module in `grader/checks/`.
- `tests_commit` is allowed only on a `tests` lesson, and only as a full 40-character commit id.

Everything else follows from the entry:

- the page column, because the page reads `lessons.json`;
- the CSV column, because `Roster` adds any missing lesson column when it saves [15];
- the facilitator page's exercise list, because it also reads `lessons.json` [29];
- the grader, because it loops over `lessons.load` [13].

### Choosing the level

| `check` | What runs | Source |
|---|---|---|
| `none` | Nothing. Each pull request is recorded as *submitted*, with the reason "a facilitator marks it" | `submissions.py:20,117-118` [14] |
| `build` | `./gradlew assemble` in the shallowest folder that has a Gradle wrapper or build file | [5][7] |
| `tests` | Copies `grader/fixtures/<key>/` over the submission, replacing any file at the same path, then runs `./gradlew test` | [6][7] |
| custom | `check(ws, lesson)` in `grader/checks/<name>.py`. It returns `(passed, reasons)` or raises `CheckFailed`. The module is found by its file name; nothing else needs registering | [4] |

Points that matter when choosing:

- **`build` and `tests` are Gradle-only.** They need a `gradlew` wrapper and run with the JDKs the grade job installs: 17, 21 and 25 [7][18]. A Maven or Node exercise needs a custom check or `none` (see Gap 2).
- **`pin-tests` replaces only a generic level.** It refuses a lesson that has a custom check [8]. It fetches the exercise repository at a commit (the latest by default). It copies every `src/test/` folder into `grader/fixtures/<key>/`, sets `check` to `tests` and records `tests_commit` [8][9]. It never runs the repository's code.
- **Changing a lesson's level regrades only that lesson.** A lesson's version is a hash of its check name, its check module, the shared toolkit and executor, and its fixture files [3]. Any result recorded under an older version is graded again on the next run [14]. So "start at `none`, raise the level later" is safe [38].
- **A custom check may import only from the toolkit.** It must run participant code only through `ws.run`/`ws.start`. `test_lessons.py` and `test_boundaries.py` fail otherwise [35][36].

### The steps

The `add-lesson` skill [37] is the current procedure. In short:

1. Read the exercise's problem statement and its existing pull requests.
2. Agree the level. Try `tests` with `pin-tests` first when the repository's `src/test/` defines "correct".
3. Add the entry to `lessons.json`.
4. Run `pin-tests`, or write the custom module. Every failure reason should be a sentence the participant can act on.
5. Prove it in `test_checks.py` (section 2 below).
6. Optionally, record existing submissions with `grade --no-run` and then `apply`. See Gap 6 before doing this.
7. Open a pull request. The *Protect main* ruleset requires one and requires the `fast` and `slow` checks to pass [24].
8. Optionally, connect the exercise repository: run `grader/setup-pr-trigger.sh` [23]. Without it the lesson is graded by the daily run at 03:17 UTC [17], or when a facilitator presses **Grade now** (added after this note).
9. After merging, run *Actions → Grade submissions → Run workflow*. Merging to `main` does **not** start grading. `grade.yml` starts only on `repository_dispatch`, on its schedule, or by hand [17].

### Things a new host should know

- **Pull requests from the exercise repository's owner do not count.** The same goes for bots, and for pull requests closed without merging [11]. If Atul owns an exercise repository, a test pull request he opens himself will never appear on the board.
- **The exercise repository must be public.** Pull requests are listed with the grade job's own token, and code is fetched with plain `git fetch` and no credentials [16][18]. See Gap 1.
- **Moving hosts means a new token and a new connection step for every exercise repository.** `setup-pr-trigger.sh` writes the leaderboard's name into each repository's workflow file. The token's resource owner must be the leaderboard's owner [23]. GitHub accepts `POST /repos/{owner}/{repo}/dispatches` from a fine-grained token only with **Contents: write** on the target repository [43]. That is why the token can also change files, which the wizard warns about [23].
- **You can connect only repositories you administer.** The wizard skips any repository where you are not an admin [23]. FizzBuzz lives in `meswright/excersize-1` [1]. Unless its owner adds the workflow, that lesson is graded only once a day.

## 2. Testing a lesson, in detail

### What exists

- **`lessons.json` is valid.** `test_the_real_lessons_file_is_valid` loads the real file [35]. Run it alone with `-p test_lessons.py`.
- **Check structure.** Each check is a module named after itself and imports only the shared modules [35]. Processes start only where they are allowed [36].
- **Check behaviour.** `grader/tests/test_checks.py` holds this. `LocalFolder` is a stand-in source whose one "pull request" is a folder on disk. `run_check(check, folder, lesson_key)` builds a `Lesson` and calls `grade.grade_submission`, the same function real grading uses, with the same workspace, sandbox and error handling [31][12]. The `lesson_key` argument picks the fixture folder. A `tests` lesson can therefore be tested as `run_check('tests', folder, '<key>')`, as `test_level_tests_uses_the_lessons_fixture_files` does [31].
- **Pinning.** `test_exercise_tests.py` covers `pin-tests` against throwaway git repositories, so a pinned lesson needs no new pinning tests.

### Writing the test for a new lesson

Follow `GradleCheckTests` [31]:

1. Decorate the class with `@slow` and `@unittest.skipUnless(checks.jdks(), 'needs a JDK')`.
2. Use trusted inputs only. The starter can be cloned in `setUpClass`, as `STARTERS` does. A reference submission can be written by a helper, such as `reference_upgrade`, or kept small under `grader/tests/data/<key>/` [31][37].
3. Assert that a good submission passes. Assert that a bad one fails **with the specific reason**, for example `assertIn('Spring Boot 3.5', text)`.
4. Never build a real participant's pull request locally [37]. Run `leaderboard.py grade` locally only with `--no-run` [38].

### How the tiers run

| Where | Command | What runs |
|---|---|---|
| Before each commit, if turned on with `git config core.hooksPath .githooks` | `GRADER_FAST=1 python3 -m unittest discover grader/tests`, plus `ruff` | Fast tier only: `@slow` tests are skipped [32][34] |
| *Test the grader*, `fast` job | Same, on every pull request | Fast tier and lint [33] |
| *Test the grader*, `slow` job | `python3 -m unittest discover -v grader/tests` with JDK 17/21/25, Node, Playwright and the `grader-sandbox` user | Everything, including the check tests run as the sandbox user [33] |
| Your machine | The same command, with no `GRADER_FAST` | Everything this machine can run. Tests skip themselves without a JDK, network or Docker [31] |

I checked the fast tier on a scratch copy of the repository. With a new `none` lesson, and again with a new untested custom check, all 309 tests passed (32 skipped) in about 59 seconds. **Nothing fails when a check has no tests** (Gap 7).

## 3. How the workflows work, in detail

### Participant path

```
exercise repository                         leaderboard repository (main)
───────────────────                         ─────────────────────────────
PR opened / new commit / closed / reopened
        │  notify-leaderboard.yml (pull_request_target; base copy; no checkout)
        │  gh api repos/<leaderboard>/dispatches  event_type=submission
        │  (LEADERBOARD_TOKEN: fine-grained, Contents: write)
        ▼
  repository_dispatch ──────────────────►  grade.yml  "Grade submissions"
  (also: daily cron 03:17 UTC, Run workflow)     concurrency group "grade", queue: max
                                                 │
                                                 ├─ job grade   (contents: read, no secrets)
                                                 │    checkout main; JDK 17/21/25; useradd grader-sandbox
                                                 │    leaderboard.py grade  → grader/results.json
                                                 │    upload-artifact "results"
                                                 │
                                                 └─ job publish (contents: read; ssh-key = deploy key)
                                                      download-artifact
                                                      run_and_push.sh: leaderboard.py apply → participants.csv
                                                      git push origin HEAD:main  (deploy key bypasses ruleset)
                                                                   │
                                                                   ▼  push to main
                                                 pages.yml "Publish the page"
                                                      copy index.html, facilitator.html, scoring.js,
                                                      participants.csv, lessons.json, dashboard.json
                                                      upload-pages-artifact → deploy-pages
```

Each step, with its evidence:

1. **The trigger.** The exercise repository runs `notify-leaderboard.yml` on `pull_request_target` for `opened`, `synchronize`, `reopened` and `closed` [22]. That event "runs in the context of the default branch of the base repository" [41], so a participant cannot edit the workflow that runs. The workflow checks out no code. It sends `event_type=submission` with `client_payload[pr]` [22]. GitHub allows at most 10 top-level payload properties, under 64 KB in total [42].
2. **Receiving it.** `grade.yml` listens for `repository_dispatch: types: [submission]`, a daily `schedule`, and `workflow_dispatch` with an optional `only` [17]. GitHub starts `repository_dispatch` and `schedule` runs only from a workflow file on the **default branch** [41].
3. **Queueing.** `concurrency: group: grade`, `cancel-in-progress: false`, `queue: max` [17]. GitHub documents `queue: max` as "Up to 100 jobs or workflow runs can be `pending`", and says it cannot be combined with `cancel-in-progress: true` [45]. Without it, only one run may wait and a newer one cancels it [45].
4. **Grading.** The `grade` job [18]:
   - checks out `main`, not the event's commit, so a run that waited sees earlier results;
   - has only `contents: read` and no secrets;
   - runs submissions as a separate `grader-sandbox` user.

   `grade_all` loads each lesson's check. A broken check module skips only that lesson. The job lists pull requests (an unreachable repository skips only that repository), records each author's display name, and grades each pull request that `needs_grading`: the lesson is automated and has no result for this commit and version [13][14]. A grader error is recorded as `passed: None` and retried next run [12].
5. **Saving.** The `publish` job never runs participant code. It checks out with `ssh-key: LEADERBOARD_DEPLOY_KEY` and runs `run_and_push.sh` [19].
   - The script resets to `origin/main` and runs `leaderboard.py apply <results.json>`. That refuses a malformed file and writes `participants.csv` [15].
   - It stages `participants.csv`, `grader/results.json`, `grader/history.json` and `grader/batches.json`, then pushes.
   - If someone else pushed first, it retries up to 5 times [20].
   - A deploy key is "an SSH key that grants access to a single repository", read-only unless write access is ticked [46]. The ruleset lists `DeployKey` as a bypass actor [24][47].
6. **Why the push publishes the page.** "Events triggered by the `GITHUB_TOKEN` will not create a new workflow run", except `workflow_dispatch` and `repository_dispatch` [44]. A deploy-key push is not the `GITHUB_TOKEN`, so the `push` trigger in `pages.yml` fires [21]. `pages.yml` deploys with `pages: write` and `id-token: write` to the `github-pages` environment, using `upload-pages-artifact` and `deploy-pages` [21][48]. Its own concurrency group, `pages`, also uses `queue: max`.

### Facilitator path

```
facilitator.html (on GitHub Pages)
  pick person → act → rows wait in "Changes" → Send
        │  opens github.com/<repo>/issues/new?template=facilitator-changes.yml&title=…&batch=<id>&changes=<rows>
        ▼
  facilitator presses "Submit new issue"  (title "Facilitator: Changes")
        │  issues: opened
        ▼
changes-from-issues.yml
  job read    if title starts "Facilitator: " and author_association ∈ OWNER/MEMBER/COLLABORATOR
              issue_form.py: GET /collaborators/<login>/permission → admin|maintain|write?
              → args = ["batch", <id>, <JSON rows>]
  job change  uses facilitator-action.yml (secret: LEADERBOARD_DEPLOY_KEY only)
              run_and_push.sh 'leaderboard.py --args-json "$ARGS"'
                 → leaderboard.py batch: each row applied on its own; outcomes → grader/batches.json,
                   changes → grader/history.json; participants.csv
              git push origin HEAD:main (deploy key)  ──►  pages.yml (as above)
  job answer  comment with the summary, close (completed / not planned), lock
        ▲
facilitator.html polls GET /repos/<repo>/contents/grader/batches.json?ref=main (no token),
after 30 s and then once a minute while anything waits; shows Done / Not done per row
```

Each step, with its evidence:

1. **Sending.** The page works out the repository from `<owner>.github.io/<repo>/`, or from `?repo=` [29]. Send builds a URL with `template=facilitator-changes.yml` plus the `batch` and `changes` field ids [29][30]. GitHub supports `template` in an issue URL and lets URL parameters fill issue-form fields [50]. The facilitator must still press **Submit new issue**. Opening an issue through the API needs a token (see `facilitator-batching.md`).
2. **Who may change things.** The `read` job runs only for `OWNER`, `MEMBER` or `COLLABORATOR` authors [25]. `issue_form.py` then asks GitHub for the author's permission and accepts only `admin`, `maintain` or `write` [28]. `issues` events also fire only from the default branch's workflow file [41].
3. **Making the change.** The `change` job calls the reusable `facilitator-action.yml` and passes only the deploy key. Secrets reach a called workflow only when passed explicitly [53]. The inputs arrive as a JSON array and go straight to Python, so no shell ever reads them [26][9].
   - `leaderboard.py batch` applies each row on its own. A refused row does not stop the others.
   - It records each row's outcome in `grader/batches.json` and each change, with its id, in `grader/history.json` [10].
   - `run_and_push.sh` pushes as in the participant path [20].
4. **Answering.** The `answer` job comments with the run's summary. It closes the issue as *completed*, or *not planned* if nothing changed, and then locks it [25].
5. **Following.** The page reads `grader/batches.json` through the contents API without a token. It waits 30 seconds, then checks once a minute, and only while a row is still waiting [29]. Unauthenticated calls are limited to 60 an hour per IP address [52]. A `304` answer is free only for authorised requests [54]. The page's code comment already allows for this.
6. **The Actions-tab forms** (`facilitator-*.yml`) skip steps 1, 2 and 4. Each form passes its JSON argument array straight to `facilitator-action.yml`, for example `["mark", person, lesson, status]` [27]. Only users with write access can run `workflow_dispatch`.

## Gaps found

1. **Undocumented: exercise repositories must be public.** `executor.fetch` runs `git fetch <https url>` with no credentials [16]. `grade.py` lists pull requests with the grade job's token, which is scoped to the leaderboard repository [18][11]. Neither README "Lessons" [38] nor the skill [37] says so. Only the unbuilt design in `lessons-by-workflow.md` mentions "must be public".
2. **README says `build` means "the submission builds". The code accepts only Gradle, on JDK 17/21/25.** README: [38] (`README.md:73`). Code: `build.py` calls `gradle_project` and `gradle`, which require `gradlew` [5][7]. JDKs: `grade.yml:46-52` [18]. The skill says "Gradle project builds" correctly. README should too, and should name the JDKs.
3. **README's "by hand" route stops at editing `lessons.json`.** `README.md:83` [38] says to add the entry with `"check": "none"`. It does not say to open a pull request (required by the ruleset [24]), connect the repository with `setup-pr-trigger.sh`, or run *Grade submissions* afterwards. Only a comment in `setup-pr-trigger.sh:205` says to run it again after adding a lesson [23].
4. **`FACILITATOR.md` lists exercise keys by hand.** `FACILITATOR.md:40` names the four current keys [39]. Neither the skill nor the README says to update it, so it goes out of date with every new lesson.
5. **Skill step 4 says "Then only step 5 remains" after `pin-tests`.** `SKILL.md:33` [37]. Steps 6 to 8 (record, pull request, connect) still apply. It means "only proving it remains", but a reader could skip connecting the repository.
6. **Skill step 6 commits files the grader rewrites on `main`, and is not needed.** It commits `participants.csv` and `grader/results.json` from a local `grade --no-run && apply` in a pull request [37]. The grader and facilitator forms push those same files to `main` on every run [20][19], so the pull request is likely to conflict. After the merge, one *Grade submissions* run records every submission anyway. A `none` lesson is recorded as submitted, and an automated lesson is graded [13][14]. Simpler: merge only `lessons.json` (and any fixtures and checks), then press **Run workflow**. If you do run it locally, set `GH_TOKEN=$(gh auth token)`: `grade.py` uses it [11], and without it you are limited to 60 requests an hour [52].
7. **Nothing enforces a test per check, and a skip can pass the required check.** On a scratch copy I added an untested custom check and a lesson using it. The fast suite still passed: 309 tests, OK. `GradleCheckTests.setUpClass` raises `SkipTest` when it cannot clone the starters [31] (`test_checks.py:139`). A network failure in CI therefore turns the required `slow` job green without running the check tests [33]. The skill's "running, not skipped" [37] depends on someone reading the output.
8. **The default branch must be called `main`, and setup never says so.** `main` is written into `grade.yml:41` [18], `pages.yml:8,32` [21], `run_and_push.sh:17-18,35` [20] and `facilitator.html:199` [29]. The ruleset targets `~DEFAULT_BRANCH` [24][47]. `repository_dispatch`, `schedule` and `issues` fire only from the default branch [41]. A copy with another default branch would accept events but save and read the wrong branch.
9. **The facilitator page needs a public repository and a `github.io` project address.** `repoFromLocation` recognises only `<owner>.github.io/<repo>/`. Anything else needs `?repo=` [29]. `readState` treats a `404` as "empty" [29] (`facilitator.html:201`). On a private repository, without a token, the page would quietly show no history and never see a batch finish. That matters if Atul uses a custom domain or makes the repository private.
10. **Hand-over: every exercise repository must be connected again, and some cannot be.** The leaderboard's name is written into each exercise repository's workflow at setup [23] (`setup-pr-trigger.sh:245`). The token belongs to the leaderboard's owner [23]. A new host must therefore re-run the wizard as an admin of each exercise repository. `meswright/excersize-1` [1] stays on the daily run unless its owner adds the workflow. No document covers moving to a new host.
11. **"An issue from anyone else starts nothing" is not literally true.** README step 4 [40] and `FACILITATOR.md:7` say this. In fact the workflow run is still created, and its jobs are skipped by the `if:` on `read` [25]. The outcome is right: nothing changes and nothing is answered. A host checking the Actions tab will still see skipped runs.
12. **A custom repository role is refused even if it includes write access.** `issue_form.permission` prefers `role_name` over `permission` [28]. GitHub says `role_name` "provides the name of the assigned role, including custom roles" [51]. A custom role's name is not in `{admin, maintain, write}`, so it is refused. This only matters if the leaderboard moves to an organisation that uses custom roles.
13. **The wizard creates a label that README's manual steps omit.** `setup-leaderboard.sh:291-296` creates the `facilitator` label [24]; README's manual steps [40] do not. This is harmless: GitHub silently skips a template label that does not exist [49].
14. **Earlier notes, partly out of date.**
    - `lessons-by-workflow.md` §1 says `run_and_push.sh` stages only three files. It now also stages `grader/batches.json` [20]. Its main point still stands: `lessons.json` and `grader/fixtures/` are not staged.
    - It cites `roster.py:60-66`. That code is now at lines 62-70 [15].
    - `adding-lessons.md` is still accurate. Steps 2 to 4 (the `spec` check) are still unbuilt: there is no `grader/checks/spec.py`.

## Sources

Repository files (on `main` at 588d237):

1. `lessons.json:1-26`
2. `grader/lessons.py:23,78-111` (fields and validation)
3. `grader/lessons.py:48-63` (`Lesson.version`)
4. `grader/checks/__init__.py:1-35` (check discovery, `check(ws, lesson)` contract)
5. `grader/checks/build.py:5-7`
6. `grader/checks/tests.py:6-10`
7. `grader/checks/toolkit.py:57-61,87-112` (`gradle_project`, `gradle`, `overlay`)
8. `grader/exercise_tests.py:19,26-59` (`pin`, refuses custom checks)
9. `grader/leaderboard.py:97-104,167-170` (`pin-tests`, `grade`, `--args-json`)
10. `grader/leaderboard.py:127-164` (`run_batch`)
11. `grader/grade.py:41-61` (token, `pull_requests`: owner, bots and withdrawn excluded)
12. `grader/grade.py:70-81` (`grade_submission`)
13. `grader/grade.py:84-122` (`grade_all`)
14. `grader/submissions.py:20,94-123` (`needs_grading`, `record`)
15. `grader/roster.py:62-70,374-379` (missing lesson columns added; `apply_results`)
16. `grader/executor.py:65-72` (`fetch`)
17. `.github/workflows/grade.yml:12-26` (triggers, concurrency)
18. `.github/workflows/grade.yml:33-72` (`grade` job)
19. `.github/workflows/grade.yml:74-89` (`publish` job)
20. `grader/run_and_push.sh:16-41` (files staged at line 26)
21. `.github/workflows/pages.yml:1-40`
22. `grader/exercise-repo/notify-leaderboard.yml:1-29`
23. `grader/setup-pr-trigger.sh:205,226-258,300-317`
24. `grader/setup-leaderboard.sh:252-296` (ruleset, Pages, approval, label)
25. `.github/workflows/changes-from-issues.yml:20-81`
26. `.github/workflows/facilitator-action.yml:23-55`
27. `.github/workflows/facilitator-mark.yml:1-23`
28. `grader/issue_form.py:22-36,79-107`
29. `facilitator.html:167-181,196-206,476,520-535`
30. `.github/ISSUE_TEMPLATE/facilitator-changes.yml:1-25`
31. `grader/tests/test_checks.py:26-30,88-103,128-195` (`LocalFolder`, `run_check`, `GradleCheckTests`, `SkipTest` at 139)
32. `grader/tests/tiers.py:1-9`
33. `.github/workflows/test.yml:7-70`
34. `.githooks/pre-commit:1-16`
35. `grader/tests/test_lessons.py:121-147`
36. `grader/tests/test_boundaries.py:14-24,59`
37. `.claude/skills/add-lesson/SKILL.md:10,25-41`
38. `README.md:61-83,96-97`
39. `FACILITATOR.md:40`
40. `README.md:43-57`

GitHub Docs (read 16 November 2026):

41. Events that trigger workflows (`repository_dispatch`, `schedule`, `issues`: default branch only; `pull_request_target` context): https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows
42. Create a repository dispatch event (`client_payload` limits): https://docs.github.com/en/rest/repos/repos#create-a-repository-dispatch-event
43. Permissions required for fine-grained personal access tokens (`POST /repos/{owner}/{repo}/dispatches`: Contents, write): https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens
44. `GITHUB_TOKEN` (its events create no new runs, except `workflow_dispatch` and `repository_dispatch`): https://docs.github.com/en/actions/concepts/security/github_token
45. Control the concurrency of workflows and jobs (`queue: max`): https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/control-the-concurrency-of-workflows-and-jobs
46. Managing deploy keys: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys
47. Repository rulesets REST API (`bypass_actors.actor_type: DeployKey`, `~DEFAULT_BRANCH`): https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset
48. Using custom workflows with GitHub Pages: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
49. Syntax for issue forms (`labels` that do not exist are not added): https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
50. Creating an issue from a URL query: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue#creating-an-issue-from-a-url-query
51. Get repository permissions for a user (`permission` vs `role_name`): https://docs.github.com/en/rest/collaborators/collaborators#get-repository-permissions-for-a-user
52. Rate limits for the REST API (60 per hour unauthenticated): https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
53. Reuse workflows (passing secrets): https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows
54. Best practices for using the REST API (conditional requests): https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
