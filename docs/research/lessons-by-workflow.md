# Adding lessons from a form, and checking treatments that tests cannot

*Research note, 16 November 2026. Audience: project lead and facilitators. Builds on `adding-lessons.md` (12 Nov), which covers why we pin upstream tests and why GitHub Classroom is not an option. That note's step 1, `pin-tests`, now exists.*

> **Status (16 Nov 2026).** Not built yet. `run_and_push.sh` now also saves `grader/batches.json` (four files, not three), and the `roster.py` lines cited have moved; the point stands. The four blockers it found in the code still stand (lessons added by a workflow would not be saved; two lessons on one repository would share results; lesson settings are not in its version; tests can be switched off in `build.gradle`).

**Short answer:**

1. A **"Facilitator: Add a lesson"** form fits the existing pattern: one workflow, one issue form and one `leaderboard.py add-lesson` command. It can choose `tests`, `build` or `none` by itself. It must **never** choose or write a custom check. When no generic level fits, it adds the lesson at `none` and says so. Two small code changes are needed. `run_and_push.sh` must also stage `lessons.json` and `grader/fixtures/`. Results must stop being keyed by `repo#N` alone before two lessons can share a repository.
2. **Sections** of one exercise repository become separate lessons on the same repo. Each lesson has a `tests` filter (Gradle `--tests` patterns) or a JUnit tag expression, and an optional `ref` for repos that use one branch per step.
3. Most planned treatments need **no new Python per lesson**. One more generic module, `grader/checks/spec.py`, would read a `spec` object in `lessons.json` and apply named static rules: file patterns, dependency versions, Dockerfile `FROM`, and a short list of allow-listed tools. It is the static part of the earlier note's `spec` proposal, kept in JSON because Python's standard library has no YAML parser.
4. **Containers:** keep building and running on the runner, and add run limits, labels and `docker image inspect`. Use the docker-library manifest as the "supported tag" list. Run scanners only as information, because their results change daily. RHEL "VM images" can only be approximated by UBI containers and `packer validate`.

| Treatment | Level | What it verifies | Overhead per lesson |
|---|---|---|---|
| Open source library version update | `spec` (+ `tests` if the repo has them) | resolved versions ≥ the minimums found with OSV when the lesson is written; build passes | data only, ~20 min |
| Container base image upgrade | `container_image` today; `spec` `dockerfile_from` + build for new lessons | `FROM` matches the approved tag pattern; image builds; not root | data only for static; HTTP smoke test stays custom |
| Framework major-version upgrade | `tests` (pinned) + `spec` | the repo's tests pass; framework ≥ X; forbidden imports gone (`javax.*`) | data, ~30 min |
| SAST vulnerability remediation | `spec` `semgrep` rule | zero findings for the pinned local rule file | rule file + data, ~30 min |
| Middleware and runtime upgrade | `spec` + `build` | version strings in build/Dockerfile/config; builds | data; `none` if the middleware is outside the repo |
| Unmaintained library replacement | `spec` + `tests` | old coordinate absent, replacement present, tests pass | data |
| Java major / minor upgrade | `spec` + `build` | toolchain/`release` ≥ N; Temurin tag; builds on that JDK | data |
| React / TypeScript / Angular major / minor | `spec` (`package.json` + lockfile) | resolved versions in `package-lock.json` | data; a Node build needs one more generic module (`npm_build`) |
| RHEL major / minor ("No of VM images") | `spec` + `none` checklist | `FROM` is `ubi<N>`; Packer templates name RHEL N and pass `packer validate -syntax-only` | data; booting a VM is out of reach |
| Lightspeed, Release on Demand, COIN, Delphyne, other standard tooling | `spec` file markers + `none` checklist | config file exists and matches a marker regex | data; a facilitator confirms the integration |
| Renovate adoption | `spec` `tool: renovate-config-validator` | `renovate.json` exists and validates | data |
| Vault adoption | `spec` + `none` checklist | no plaintext secrets; Vault client dependency/config present | data; a live Vault test is custom |
| GitHub migration | `spec` `tool: actionlint` + `none` | workflows exist and lint clean; old CI file removed | data; "a run succeeded" stays human-judged |
| Automated test asset improvement | custom (`test_quality`), else `none` | coverage/mutation score above a baseline | 2 to 4 h once, then data |
| Build and deployment workflow automation | `spec` (actionlint + regex) + `none` | workflow builds and tests; lints clean | data |

---

## 1. A "Facilitator: Add a lesson" form

### What exists

Each form is a `facilitator-*.yml` that passes a JSON argument array to `facilitator-action.yml`. That workflow runs `leaderboard.py --args-json` through `run_and_push.sh` and pushes with the deploy key, which is the only identity allowed to push to the protected `main`. The issue form path, `changes-from-issues.yml` with `grader/issue_form.py`, maps form labels to the same arguments, and only for write, maintain or admin collaborators. ADR 0002 requires one workflow per form. `grader/tests/test_issue_form.py` and the walkthrough keep `FORMS`, `facilitator-forms.js`, `walkthrough/steps.js` and the workflow files consistent.

Three gaps:

- `run_and_push.sh` stages only `participants.csv`, `grader/results.json` and `grader/history.json`. A new lesson would therefore commit nothing.
- `exercise_tests.pin` accepts only a full commit id or `HEAD`.
- `submissions.key` is `f'{lesson.repo}#{pr.number}'`, so two lessons on one repo would overwrite each other's results (see §2).

### Proposed workflow

```yaml
# .github/workflows/facilitator-add-lesson.yml
name: 'Facilitator: Add a lesson'
on:
  workflow_dispatch:
    inputs:
      repo:   {description: 'Exercise repository, owner/name (must be public)', required: true}
      key:    {description: 'Column name: lowercase letters, digits and _', required: true}
      label:  {description: 'Name shown on the page', required: true}
      check:
        description: 'How to grade. "auto" uses the repository''s tests if it has any'
        type: choice
        options: [auto, tests, build, none]
        default: auto
      commit: {description: 'Commit or branch to take the tests from (default: latest)', required: false}
permissions:
  contents: read
jobs:
  run:
    uses: ./.github/workflows/facilitator-action.yml
    secrets:
      LEADERBOARD_DEPLOY_KEY: ${{ secrets.LEADERBOARD_DEPLOY_KEY }}
    with:
      args: '["add-lesson", ${{ toJSON(inputs.repo) }}, ${{ toJSON(inputs.key) }}, ${{ toJSON(inputs.label) }}, ${{ toJSON(inputs.check) }}, ${{ toJSON(inputs.commit) }}]'
```

The issue form `facilitator-add-lesson.yml` has the same fields, with a `dropdown` for the check. Its `FORMS` entry is:

```python
'Add a lesson': ('add-lesson', [('Repository', 'repo'), ('Column name', 'key'), ('Label', 'label'),
                                ('How to grade', 'check'), ('Commit', 'commit')]),
```

with `DEFAULTS['check'] = 'auto'`.

`facilitator-action.yml` needs `GH_TOKEN: ${{ github.token }}` in the change step for the repository lookup. Its `contents: read` is enough, because public repositories are readable. Only the deploy key writes.

### What `add-lesson` does (new function next to `exercise_tests.pin`)

1. **Validate the inputs** with the same rules as `lessons.load`: key format, key not reserved or already used, label present. Then call `GET /repos/{repo}`. Refuse if it fails or if `private` is true. Warn if `archived` is true. These fields are in the [Get a repository](https://docs.github.com/en/rest/repos/repos#get-a-repository) response. The docs do not say whether a private repository returns 404 to callers without access. Either way it is refused, because the clone in step 2 fails.
2. **Fetch** the repo at `commit`, or its default branch, with `executor.fetch`. It already accepts a branch or a commit and returns the resolved SHA. This job holds the deploy key, so it **only copies files and never runs Gradle or anything from the repo**. Pinning already respects this.
3. **Choose the level** and record why:

   | Found at that commit | `auto` chooses | Reason recorded |
   |---|---|---|
   | Gradle project with `src/test/**` | `tests` (pin) | "N test files under src/test at abc1234" |
   | Gradle project, no tests | `build` | "no tests in the repository; only the build is checked" |
   | No Gradle project (Node, Dockerfile only, docs only) | `none` | "no Gradle project: needs a facilitator or a custom check" |

   An explicit `tests` that finds no tests fails with the usual message, `❌ Nothing was changed`. A custom check name is never accepted from the form. Custom checks carry lesson-specific constants and need tests (ADR 0001, skill step 5), so they arrive through a pull request.
4. **Write** the entry, plus `tests_commit` and fixtures through the existing `pin` path. Then save the roster: `Roster` adds any lesson column that is missing whenever it writes (`roster.py`, `_Sheet`), so the column appears right away instead of on the next `apply`.
5. **Commit.** Extend `run_and_push.sh` to `git add lessons.json grader/fixtures`. The commit title carries the decision ("Add lesson container_v2 (tests: 7 files at abc1234)"), so `git log -- lessons.json` keeps the reason without a new field in `lessons.json`.

**Undo.** `undo` reverses roster actions only. Adding a lesson is not a roster action, so `undo` must refuse it, or the summary must say "remove it with a pull request". Do not extend the undo journal for this.

### Reporting "needs a facilitator or a custom check"

The lesson is still added, at `none`, so submissions show as *submitted* and facilitators can mark them. The run then:

- writes a `### ⚠️ Not graded automatically` section to the step summary, which the issue reply repeats, saying why;
- emits `::warning title=Needs a facilitator or a custom check::…` so the warning shows on the run list;
- links to the `add-lesson` skill as the next step ("ask Claude Code to add a check for `<key>`").

This keeps the existing rule that only real faults turn a run red.

### Handing off per-PR grading

The form cannot connect the exercise repository. That needs a secret and a workflow file on a repository the leaderboard does not own (`grader/setup-pr-trigger.sh`, which requires admin there). The summary should therefore always end with:

> **Connect `<repo>`.** Until its admin runs `grader/setup-pr-trigger.sh` (or adds `.github/workflows/notify-leaderboard.yml` and the `LEADERBOARD_TOKEN` secret), this lesson is graded once a day (03:17 UTC) or when someone runs *Grade submissions*.

The form can check `GET /repos/{repo}/contents/.github/workflows/notify-leaderboard.yml` the same way `setup-pr-trigger.sh` does (`has_hook`), and drop the paragraph when the file is already there.

**Risk.** The deploy key bypasses the ruleset, so a lesson added from the form reaches `main` without review. That is acceptable because no new code runs: pinned tests run in the sandboxed `grade` job, like any submission. The form must stay unable to add custom checks.

## 2. Tests "at each section"

### What others do

- **GitHub Classroom** (retired 28 Aug 2026; see the earlier note) defined tests per *assignment*, not per step. A multi-step exercise used several "run command" tests, each with its own optional points; for pytest, "each test is worth the suite's points divided by the number of tests" ([docs](https://docs.github.com/en/education/manage-coursework-with-github-classroom/teach-with-github-classroom/use-autograding)). Its actions set a `max-score` per step, such as `autograding-command-grader` with `command: …` and `max-score: 20`, and the reporter adds them up. The repository was archived on 6 Oct 2026 ([reporter](https://github.com/classroom-resources/autograding-grading-reporter)). The lasting idea is **one named command per section, each scored separately**.
- **Gradle** filters with `--tests`. Patterns can be a class, a method, a package wildcard or a simple name, and several `--tests` flags combine ([test filtering](https://docs.gradle.org/current/userguide/java_testing.html#test_filtering)). With a filter, the task fails if nothing matches, because `failOnNoMatchingTests` defaults to true ([TestFilter](https://docs.gradle.org/current/javadoc/org/gradle/api/tasks/testing/TestFilter.html)). That is what we want when a section's tests are missing.
- **JUnit tags.** `useJUnitPlatform { includeTags … }` ([test grouping](https://docs.gradle.org/current/userguide/java_testing.html#test_grouping)) accepts tag expressions with `!`, `&`, `|`, `any()` and `none()` ([JUnit tags](https://docs.junit.org/6.0.0/running-tests/tags.html)). Gradle has no command-line flag for tags, so the grader would apply them through an init script.
- **Maven** uses `-Dtest=Class,Pattern*,!Excluded`. Selecting single methods works only for JUnit 4 and TestNG ([Surefire](https://maven.apache.org/surefire/maven-surefire-plugin/examples/single-test.html)). The grader is Gradle-only today.

### Common layouts, mapped

| Layout | Lesson per section | Test source |
|---|---|---|
| Folders per section (`step1/`, `step2/`, each its own project) | `spec.dir: "step2"` | pin `step2/src/test` only |
| One project, test classes per section (`Step2Test`) | `tests: ["*Step2*"]` | pin all of `src/test`; filter when running |
| Tagged tests (`@Tag("step2")`) | `tags: "step2"`, or `"step1 | step2"` for cumulative sections | pin all; init-script `includeTags` |
| Branch or tag per step (`step-2`, `solution-2`) | `ref: "step-2"` | pin from that ref |

### Minimal schema change

```json
{"key": "orders_s2", "label": "Orders: step 2", "repo": "acme/orders",
 "check": "tests", "tests_commit": "<sha>",
 "tests": ["com.acme.orders.Step2*"], "tags": "", "dir": "", "base": "step-2"}
```

- `tests` holds a list of Gradle `--tests` patterns, passed as repeated `--tests` arguments to `gradle test`.
- `tags` holds a JUnit tag expression, passed through `-I grader/junit-tags.gradle -Pgrader.tags=…`.
- `dir` is the subfolder used as the project instead of `gradle_project(root)`'s shallowest match.
- `base` grades only PRs whose `base.ref` is this branch. It is needed when steps are branches and PRs target them.

All of these must enter `Lesson.version`, or changing a filter will not regrade anyone.

**`pin-tests` changes.** Accept a branch or tag and record the resolved SHA. With `dir`, copy only `<dir>/src/test`. With `tests`, keep copying the **whole** `src/test`, because shared helpers and base classes live there. The filter decides what runs, not what is copied.

**Required fixes before two lessons share a repo:**

- `submissions.key` must include the lesson key, for example `orders_s2:acme/orders#3`, with a one-off migration of `results.json`.
- `lessons.load` must reject two lessons on the same repo unless they differ in `tests`, `tags`, `dir` or `base`.

Cumulative sections need no special support: if one PR completes steps 1 to 3, each step's lesson passes on the same PR.

**Risk, already present today.** The participant controls `build.gradle`. They could disable the `test` task or set `ignoreFailures`. Gradle writes JUnit XML results under `build/test-results/`, so the `tests` check should confirm from that XML that every pinned test class in the filter actually ran and passed, rather than trusting the exit code alone.

## 3. Treatments without suitable tests

### One generic module: `grader/checks/spec.py`

Under ADR 0001, this is one more module. Every lesson that uses it shares the same code, and its data lives in `lessons.json`:

```json
{"key": "lib_update", "label": "Library update", "repo": "acme/svc", "check": "spec",
 "spec": {
   "build": true, "tests": false,
   "rules": [
     {"type": "dependency", "name": "org.apache.commons:commons-text", "min": "1.10.0"},
     {"type": "dependency_absent", "name": "commons-lang:commons-lang"},
     {"type": "file_exists", "path": "renovate.json"},
     {"type": "file_matches", "glob": "**/build.gradle*", "regex": "languageVersion\\s*=\\s*JavaLanguageVersion\\.of\\((2[1-9])\\)"},
     {"type": "file_not_matches", "glob": "src/main/**/*.java", "regex": "import javax\\.(persistence|validation)"},
     {"type": "dockerfile_from", "stage": "final", "regex": "eclipse-temurin:21(\\.[\\d._]+)?-jre-(noble|ubi9-minimal)"},
     {"type": "npm_dependency", "name": "@angular/core", "min": "18.0.0"},
     {"type": "tool", "name": "actionlint"},
     {"type": "tool", "name": "renovate-config-validator"},
     {"type": "semgrep", "config": "semgrep.yml", "max_findings": 0}
   ],
   "manual": ["Vault policy grants read-only on secret/data/svc", "Release on Demand pipeline registered"]
 }}
```

- **Rules are named types, not free-form commands.** `tool` takes only names from a fixed table inside `spec.py`, each with a pinned version and exact arguments, so nothing in `lessons.json` reaches a shell. Every rule's failure is a sentence the participant can act on.
- **Dependency versions** come from what the build actually produced, never from text the participant wrote. For Spring Boot that is the jar's `BOOT-INF/lib/*.jar` names, the "jar_dependency" idea in the earlier note. Gradle's `dependencies --configuration runtimeClasspath` prints a text tree only ([docs](https://docs.gradle.org/current/userguide/viewing_debugging_dependencies.html)). For npm the source is `package-lock.json`. `npm ls --all --json` also works ([docs](https://docs.npmjs.com/cli/v10/commands/npm-ls)) but needs an install first. For Maven, `versions:display-dependency-updates` lists newer versions ([docs](https://www.mojohaus.org/versions/versions-maven-plugin/display-dependency-updates-mojo.html)), which is useful when authoring, not for a pass/fail rule.
- **Vulnerabilities are checked when the lesson is written, not when it is graded.** OSV's [`POST /v1/query`](https://google.github.io/osv.dev/post-v1-query/) and [`/v1/querybatch`](https://google.github.io/osv.dev/post-v1-querybatch/) take package, ecosystem and version, and the docs show no API key. GitHub's [global advisories API](https://docs.github.com/en/rest/security-advisories/global-advisories) filters by `ecosystem`, `affects=pkg@ver` and `severity`. Claude or the facilitator runs these once and writes the resulting **minimum versions** as `dependency` rules. A live "no known vulns" rule would change results without a version change, the same problem the earlier note found with scan tables. The [Dependabot alerts API](https://docs.github.com/en/rest/dependabot/alerts) reads a repository's alerts, and its docs do not say that PR branches are covered. It needs `security_events` (or `public_repo`) scope, so it does not fit a fork PR.
- **SAST.** `semgrep scan --config <file> --error --metrics=off --json` exits 1 on findings and runs local YAML rules ([CLI reference](https://docs.semgrep.dev/cli-reference)). The rule file is pinned under `grader/fixtures/<key>/`, so it counts toward the lesson version. CodeQL "is free to use on public repositories" ([docs](https://docs.github.com/en/code-security/codeql-cli/getting-started-with-the-codeql-cli/about-the-codeql-cli)) but needs a database build per submission, which is too slow here. SpotBugs runs as Gradle tasks (`spotbugsMain`) ([docs](https://spotbugs.readthedocs.io/en/latest/gradle.html)), but only if the participant's build applies the plugin. Prefer Semgrep.
- **Renovate.** `npx --yes --package renovate -- renovate-config-validator` checks the default config locations and exits non-zero on warnings or errors ([docs](https://docs.renovatebot.com/config-validation/)). Node is on the runner ([image readme](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)). Pin the Renovate version.
- **Workflows.** actionlint checks syntax, expression types and `run:` scripts through shellcheck, and flags script injection (MIT licence) ([repo](https://github.com/rhysd/actionlint)). Whether "a run on the PR succeeded" cannot be trusted. `GET /actions/runs?head_sha=` can find the run ([docs](https://docs.github.com/en/rest/actions/workflow-runs)). But a fork PR's runs need approval, and the participant controls the workflow, so it can be edited to pass (earlier note, §4). Keep that item in `manual`. For migrations, [GitHub Actions Importer](https://docs.github.com/en/actions/tutorials/migrate-to-github-actions/automated-migrations/use-github-actions-importer) supports Jenkins, GitLab, Azure DevOps, CircleCI, Travis and Bamboo. A rule "Jenkinsfile removed, `.github/workflows/*.yml` present, actionlint clean" covers the checkable part.
- **Vault.** A dev server (`vault server -dev`) is in-memory, unsealed, listens on `127.0.0.1:8200` and mounts KV v2 at `secret/`; it is "insecure" and for development only ([docs](https://developer.hashicorp.com/vault/docs/concepts/dev-server)). It would let a custom check start the app with secrets only in Vault. That is worth doing only if Vault becomes a recurring lesson. Until then: `file_not_matches` for literal passwords in `application*.{properties,yml}`, `dependency` on the Vault client, and a `manual` item.
- **Test asset improvement** needs a baseline. Coverage alone "does not check that your tests are actually able to detect faults" ([PIT](https://pitest.org/)). JaCoCo reports and `jacocoTestCoverageVerification` fail the build below a minimum ([Gradle JaCoCo](https://docs.gradle.org/current/userguide/jacoco_plugin.html#sec:jacoco_report_violation_rules)), but that config lives in the participant's build. A generic `test_quality` module would add JaCoCo or PIT through an init script, run starter and submission, and require a gain. That is 2 to 4 hours once. FizzBuzz's planted-bug check is the existing precedent.
- **Internal tools** (Lightspeed, Release on Demand, COIN, Delphyne, others) have no public docs here. `spec` can only check that a config file exists and matches a marker regex. Everything else goes in `manual`.

**Still `none` (d):** run succeeded, internal-tool onboarding, Vault policy, and a booted RHEL VM.

**Still custom (e):** HTTP behaviour (`rest_api`, the container smoke test), mutation or coverage gain, live Vault, and Node builds (one more *generic* `npm_build` module, not per lesson).

**Version.** `Lesson.version` must hash the lesson's `spec` object. Otherwise editing a rule regrades nobody.

## 4. Docker and containers

**Today.** `container_image.py` parses the Dockerfile statically. It requires:

- an `eclipse-temurin` base matching `(21|25)…-(jre|jdk)`;
- a multi-stage build with a JRE final stage;
- a non-root `USER`;
- a `.dockerignore` file.

It then runs `docker build`, `docker run --entrypoint id … -u`, and `toolkit.Container`, which runs `docker run -d -p 127.0.0.1:…`, followed by HTTP checks and `docker rmi`. The architecture note (§2) already recommends one Docker helper with labels, limits and prune-by-label.

**Build.** `docker buildx build` supports `--pull` ("always attempt to pull all referenced images"), `--network none|default|host` for `RUN` steps, `--label` and `--metadata-file` ([reference](https://docs.docker.com/reference/cli/docker/buildx/build/)). Use `--pull` so a cached old base cannot satisfy an upgrade lesson. Keep the default network: Gradle stages download dependencies, as the architecture note found.

**Inspect, without running.** `docker image inspect -f json` ([reference](https://docs.docker.com/reference/cli/docker/image/inspect/)) prints the image's JSON. The page does not list its fields; `Config.User`, `Config.Healthcheck` and `Config.Labels` are what a check would read, which is **unverified** against that page, so confirm them on the first run. For the OS, `docker run --rm --network none --entrypoint cat <img> /etc/os-release` and compare `ID`/`VERSION_ID` ([os-release](https://www.freedesktop.org/software/systemd/man/latest/os-release.html)). This is a cheap RHEL-version check for UBI-based images. `HEALTHCHECK` status (`starting`/`healthy`/`unhealthy`) is visible through `docker inspect` ([Dockerfile](https://docs.docker.com/reference/dockerfile/#healthcheck)). A lesson can require one and wait for `healthy` instead of polling a URL.

**Run with limits.** Use `--read-only --cap-drop ALL --security-opt no-new-privileges --memory 1g --pids-limit 256` ([run reference](https://docs.docker.com/reference/cli/docker/container/run/)). Use `--network none` only for probes that need no port, such as `id` and `os-release`, because it leaves only loopback ([none driver](https://docs.docker.com/engine/network/drivers/none/)). `--read-only` will break apps that write to their working directory, and the current lesson writes a file database. Add `--tmpfs` for the data path, or apply read-only to probes only.

**Approved tags.** The docker-library manifest [`library/eclipse-temurin`](https://github.com/docker-library/official-images/blob/master/library/eclipse-temurin) lists every supported tag, including `21-jre-ubi9-minimal`. Each library file "controls the current 'supported' set". Removed tags stay on Docker Hub but are no longer maintained ([README](https://github.com/docker-library/official-images)). A `dockerfile_from` rule with `"supported": "eclipse-temurin"` can check the tag against that file, pinned to a manifest commit to stay deterministic. Red Hat says UBI packages "come from RHEL" and are "supported like RHEL" ([catalog](https://catalog.redhat.com/software/base-images)). RHEL majors get roughly 10 years, and only some minors (for example 9.2/9.4/9.6/9.8/9.10) get extended life ([lifecycle](https://access.redhat.com/support/policy/updates/errata)). A minor-upgrade rule should therefore name the target minor, not "latest".

**Scanners** (information only; findings change daily):

| Tool | Free / offline | Gate flag |
|---|---|---|
| Trivy | Downloads its DB from `mirror.gcr.io` then `ghcr.io`; `--skip-db-update` reuses a cached DB ([db](https://trivy.dev/latest/docs/configuration/db/)); "requires internet connectivity" normally ([air-gap](https://trivy.dev/latest/docs/advanced/air-gap/)) | `--severity`, `--ignore-unfixed` ([filtering](https://trivy.dev/latest/docs/configuration/filtering/)) |
| Grype | Apache-2.0 ([repo](https://github.com/anchore/grype)); `grype db import FILE` with checksum pins a DB snapshot | `--fail-on high` exits 2 ([CLI](https://oss.anchore.com/docs/reference/grype/cli/)) |
| Docker Scout | Registry analysis needs a Docker ID login ([analysis](https://docs.docker.com/scout/explore/analysis/)) | not suitable: needs a secret in the grade job |

If a scan must gate a lesson, use Grype with an imported, checksum-pinned DB, and put the DB digest in the lesson's data, so the result changes only when we change it.

**VM images.** The `ubuntu-24.04` image includes Docker 28, Buildx and Packer 1.16 ([readme](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md)). Standard runners are a fresh VM with 4 CPUs, 16 GB and 14 GB disk ([docs](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)). The docs mention nested virtualization only to rule it out on arm64 macOS, so booting a RHEL VM on Linux runners is **unverified** and should not be relied on. `packer validate -syntax-only` checks syntax without validating configuration ([docs](https://developer.hashicorp.com/packer/docs/commands/validate)). Full `validate` may need cloud credentials. "No of VM images" maps naturally to a count of Packer templates whose source-image filter matches the target RHEL version.

## Risks

- Facilitator-added lessons land unreviewed; the form must stay limited to the generic levels.
- `results.json` key migration is required before shared-repo sections can be used.
- Participants control `build.gradle`; verify JUnit XML, and add JaCoCo or PIT through an init script, never through their build.
- Live data (OSV, scanners, Docker Hub tags) makes grades drift. Pin it at authoring time.
- `tool` rules run third-party binaries on participant files in the grade job: pin versions and keep the allow-list in `spec.py`.

## First steps

1. Extend `run_and_push.sh` to stage `lessons.json` and `grader/fixtures/`. Let `pin` accept a branch or tag and record the SHA.
2. Add `add-lesson` (command, workflow, issue form, `FORMS`, walkthrough entries) with `auto|tests|build|none`, the warning summary and the hand-off paragraph.
3. Key submissions by lesson, then add `tests`/`dir`/`base` (and later `tags`) to `lessons.json` and `Lesson.version`.
4. Write `checks/spec.py` with `file_exists`, `file_matches`, `file_not_matches`, `dependency` (jar), `npm_dependency` (lockfile) and `dockerfile_from`. Then add `tool` with actionlint, renovate-config-validator and semgrep. Port `container_image`'s static rules as the proof.
5. Teach the `add-lesson` skill to draft `spec` rules (with OSV-derived minimum versions) and the `manual` checklist.
