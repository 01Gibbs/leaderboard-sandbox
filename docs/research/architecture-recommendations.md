# Five architecture recommendations, checked against primary sources

*Research note, 16 November 2026. Audience: project lead.*

> **Status (16 Nov 2026; checked 18 Nov).** Written before later work, some of which touched these areas (see the index): check the code before acting on a recommendation. Related work since: grading and pages runs now queue instead of being cancelled (`concurrency.queue: max`), and refused facilitator changes no longer fail their run.

| # | Recommendation | Verdict |
|---|---|---|
| 1 | Split an undo journal out of `roster.py`; stop keying snapshots by `id()` | Journal module: **Worth exploring**. Drop `id()` keys: **Strong** (small) |
| 2 | Docker as a third `Workspace` adapter | Adapter: **Not now**. Labels, limits and cleanup for the Docker calls we already make: **Strong** |
| 3 | One owner for the grading-run results handoff | Keep whole-file replace, and add a "started from" check: **Worth exploring**. `queue: max`: **Worth exploring** |
| 4 | Lesson version from a check's real imports, a domain-helper split, one fetch recipe | Test that enforces the import rule: **Strong**. Version from imports and the split, done together: **Worth exploring**. Fetch the PR's SHA, not `pull/N/head`: **Strong** |
| 5 | A Repository module that owns the state-file paths | **Not now**: each file already has one owner |

ADRs 0001 (one module per check) and 0002 (one workflow per form) are respected throughout. §4 explains how a helper module fits next to ADR 0001.

---

## 1. An undo journal

**Current state.** The rule "every action records the cells it changed; undo restores exactly those" (`grader/roster.py:10`) is spread across five places:

- the snapshot `self.loaded = {id(r): dict(r) ...}` (`roster.py:68`);
- the diff `_Sheet.changes` (`:89-93`);
- the replay lookup `_Sheet.locate` (`:126-134`);
- `Roster._record`, which logs before/after rows and trims the log to `HISTORY_LIMIT = 100` (`:28`, `:176-183`);
- `Roster.undo` (`:271-305`), which sorts removals and edits before re-adds (`:282-283`) and skips cells that changed again since.

**What the sources say.**

- **`id()`**: an integer "unique and constant for this object during its lifetime. Two objects with non-overlapping lifetimes may have the same `id()` value" ([Python docs](https://docs.python.org/3/library/functions.html#id)). If `merge` drops a row (`:267`), that dict is freed, and a later `new_row` reuses its address, then `changes()` would report the drop as an edit of the new row. Today this cannot happen only because `merge` keeps `drops` alive until `_record` runs (`:245-269`), and no action both removes and adds a row. Nothing enforces that.
- **SQLite's undo/redo technique** ([sqlite.org/undoredo](https://www.sqlite.org/undoredo.html)) records each change as the *inverse* statement in an `undolog`, keyed by the stable `rowid`. Undo replays one barrier-delimited step newest-first, and the replay itself becomes the redo entry. Our design matches it in shape: we store before/after rows rather than inverse statements, and one action is one step. The difference is identity. SQLite has `rowid`; our CSV has no stable row key, so `locate` re-finds rows by login or name.
- **The Command pattern's** primary source is the Gamma et al. book (*Design Patterns*, 1994), which is not freely online. Its point here is that an undoable operation stores what it needs to reverse itself. Our before/after entries already do that.

**Options.**

- **A.** Keep the code where it is, and replace the `id()` map with a list of `(row, snapshot)` pairs compared with `is`. Holding the reference keeps the row alive, so its identity cannot be reused.
- **B.** Do A, then move snapshot, diff, `locate` and the replay loop into a `journal.py` with two calls: `entry = journal.diff(sheet)` and `journal.revert(entry, sheet) -> kept`. `Roster` keeps saving, actor and timestamps.
- **C.** Store inverse operations, as SQLite does. This adds redo, which nobody has asked for, and needs a stable row key that the CSV does not have.

**Risks.** B moves the "edits before re-adds" ordering and the "changed again since" rule. The tests in `grader/tests/test_roster.py` must move with them unchanged.

**Recommendation.** Do A now (**Strong**, a few lines). Do B (**Worth exploring**) only when a second consumer appears, for example a redo or a "preview undo" on the facilitator page. Until then, the module would only move code, which is the argument ADR 0001 rejects.

## 2. Docker as a Workspace adapter

**Current state.** `Local` and `Sandbox` adapt *how a process runs as a user* (`grader/executor.py:75-116`). Docker is a host tool. `container_image.check` runs `docker build -t <tag> .` (`grader/checks/container_image.py:58`), then `docker run --rm --entrypoint id` (`:62`), then `toolkit.Container`, which runs `docker run -d -p 127.0.0.1:<port>:8080` and later `rm -f` (`toolkit.py:210-231`), and finally `docker rmi -f` (`container_image.py:70`). `tests/test_boundaries.py:24` limits `docker` to those two files.

**What the sources say.**

- **Build runs participant code.** "The `RUN` instruction will execute any commands to create a new layer" ([Dockerfile reference](https://docs.docker.com/reference/dockerfile/#run)). So `docker build` runs participant commands as the image's user, on the default build network. `RUN --network=none` exists, and `--network` on the build sets it for all `RUN` steps ([buildx build](https://docs.docker.com/reference/cli/docker/buildx/build/)). However, the lesson's Dockerfiles download Gradle dependencies in their build stage, so a no-network build would fail correct submissions.
- **Build limits** go through `--resource` (`memory=…`, `cpu-quota=…`), which "require[s] a BuildKit daemon that supports per-step resource limits" (same page). That support is unverified for the runner's Docker.
- **Run limits.** `docker run` has `--rm`, `--memory`, `--cpus`, `--pids-limit`, `--read-only`, `--cap-drop` and `--security-opt no-new-privileges` ([run reference](https://docs.docker.com/reference/cli/docker/container/run/)). `--network none` leaves "only the loopback device" ([none driver](https://docs.docker.com/engine/network/drivers/none/)). That would break the HTTP check, which needs `-p`.
- **Cleanup by label.** `--label` works on build and run. `docker system prune --filter label=<k>=<v>` removes matching "containers, images, networks, and volumes", and build cache is "always eligible" ([prune](https://docs.docker.com/reference/cli/docker/system/prune/)).
- **Rootless mode** runs "the Docker daemon and containers as a non-root user" ([rootless](https://docs.docker.com/engine/security/rootless/)). Its limits flags work only "with cgroup v2 and systemd", and `-p` does not propagate source IPs by default ([troubleshooting](https://docs.docker.com/engine/security/rootless/troubleshoot/)).
- **Runner lifetime.** GitHub-hosted runners are a fresh VM per job ([about GitHub-hosted runners](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners)), so leaked images matter mainly on local runs.

**Options.**

- **A. Docker adapter.** Its `command()` wraps every `ws.run` in `docker run -v ws:/ws`. This changes how *Gradle* runs for every lesson, which is a different and much larger project. It also does not fit build-then-serve, because the adapter interface (`command/share/stop_all/remove`) has no image lifecycle.
- **B.** One `toolkit` Docker helper owns build, run, `id -u` and cleanup. It labels everything with `grader.run=<workspace>`, adds `--memory`, `--cpus` and `--pids-limit` to `run`, and prunes by label when the check ends.
- **C.** Rootless Docker on the runner. This needs extra setup steps and cgroup v2 checks, and the gain is small on a throwaway VM.

**Recommendation.** **B, Strong.** It is small, keeps the boundary test's two files, and adds the limits Docker documents. **A: Not now.** **C: Not now.**

## 3. The results handoff

**Current state.** The `grade` job checks out `main` (`.github/workflows/grade.yml:40`), writes `grader/results.json`, and uploads it (`:67-71`). `publish` downloads it (`:83-86`). `run_and_push.sh` resets to `origin/main` (`grader/run_and_push.sh:17-18`) and runs `leaderboard.py apply`, which calls `Submissions.replace_with` and replaces the whole file (`grader/submissions.py:74-78`). The group is `grade` with `cancel-in-progress: false` (`grade.yml:23-25`).

**What the sources say.**

- **Artifacts.** Since v4, "Artifacts … are immutable" and "names must be unique", with an `overwrite` option ([upload-artifact](https://github.com/actions/upload-artifact)). Within one run the handoff is therefore exact.
- **One pending run.** "At most one job or workflow run can be `pending` in the concurrency group", and a new one replaces it. `queue: max` keeps up to 100 pending runs, first in, first out, but cannot be combined with `cancel-in-progress: true` ([workflow syntax](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#concurrency)).
- **Which commit a run sees.** For `repository_dispatch` and `schedule`, `GITHUB_SHA` is the "Last commit on default branch". For `workflow_dispatch`, it is the "Last commit on the `GITHUB_REF` branch or tag". Scheduled runs "can be delayed" and under heavy load "some queued jobs may be dropped" ([events](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows)). That commit is fixed when the event fires, so a run that waited would see stale results. `ref: main` (`grade.yml:40`) and the reset in `run_and_push.sh` correctly avoid this.

**Is whole-file replace safe?** Today it is. Only this workflow writes `results.json`: facilitator actions call `apply_results` without a file, so `Submissions.save` never runs for them (`roster.py:309-314`). The group also serializes whole runs, so no other grade run starts between this run's checkout and its publish. A `--only` run is also safe: it still starts from `main`'s file and only skips other pull requests (`grade.py:99-100`).

Replace breaks only if something else changes `results.json` on `main` mid-run, such as a merged PR or a hand fix. In that case the change is silently overwritten.

A per-entry merge sounds safer but is not. `keep_only` *deletes* withdrawn PRs (`submissions.py:123-127`), and `people` names change too. A merge would need tombstones, and it would also mix two runs' `version`s.

**Options.**

- **A.** Keep as is.
- **B.** The grade job also records the SHA-256 of the `results.json` it started from. `apply` refuses, with a clear message, if `main`'s file differs. This is compare-and-swap, owned by `Submissions.replace_with(path, base)`.
- **C.** A per-entry merge, rejected above.

There is also a separate risk: a manual `--only` run can *replace* a pending event run, so other new commits wait for the next event or the daily run. The comment at `grade.yml:8-9` already says so. `queue: max` would fix it at the cost of redundant runs.

**Recommendation.** **B, Worth exploring.** It is cheap and makes the single-writer assumption explicit. Consider `queue: max` (**Worth exploring**) if `--only` gets used during workshops.

## 4. Lesson versions, helpers and fetching

**Current state.** `Lesson.version` hashes the check's own file plus `SHARED_CODE`, which is `executor.py` and `checks/toolkit.py` (`grader/lessons.py:25`, `:47-62`). The rule "a check imports only from the SHARED modules" is documented (`grader/checks/__init__.py:12-14`) but not tested. Today it holds: every check imports only `.toolkit`.

`employee_api_checks` and `IN_MEMORY_DB` (`toolkit.py:239-265`) serve three lessons (`rest_api.py:3`, `framework_upgrade.py:7`, `container_image.py:5`). Because they live in `toolkit.py`, editing them also regrades FizzBuzz and every `build`/`tests` lesson.

Both fetchers already share one recipe: `grade.GitHub.checkout` (`grade.py:64-65`) and `exercise_tests._fetch` (`exercise_tests.py:78-82`) both call `executor.fetch` (`executor.py:65-72`). However, `checkout` fetches `pull/{number}/head`, not `pr.sha`, while `record_result` stores `pr.sha` (`submissions.py:131`). If a commit lands between listing and fetching, the newer code is graded under the older SHA. The next run regrades it, because the SHA differs, but until then the result is attached to the wrong commit.

**What the sources say.**

- **[`ast`](https://docs.python.org/3/library/ast.html)** parses source without running it. The repository already uses it for `test_boundaries.py:48-57`.
- **[`modulefinder`](https://docs.python.org/3/library/modulefinder.html)** "determine[s] the set of modules imported by a script". In CPython it scans compiled code through the private `dis._find_imports` ([source](https://github.com/python/cpython/blob/main/Lib/modulefinder.py)) and walks the whole transitive closure, standard library included.
- **`sys.modules`** ([docs](https://docs.python.org/3/library/sys.html#sys.modules)) cannot attribute imports to one check: `checks/__init__.py:23-24` imports every check at once, and imports inside functions appear only when they run.
- **Fetching by SHA.** Protocol v2 says "Wants can be anything and are not limited to advertised objects" ([gitprotocol-v2](https://git-scm.com/docs/gitprotocol-v2)). Whether a server accepts them is server policy: `uploadpack.allowReachableSHA1InWant` and `allowAnySHA1InWant` ([git-config](https://git-scm.com/docs/git-config#Documentation/git-config.txt-uploadpackallowReachableSHA1InWant)). GitHub accepts a bare SHA in practice, because `actions/checkout` fetches exactly that ([`ref-helper.ts`](https://github.com/actions/checkout/blob/main/src/ref-helper.ts)). A fork PR's head is reachable from the base repository's `refs/pull/N/head`.

**Options.**

- **A.** An `ast` test that fails if a check imports anything in `grader/` other than `checks.SHARED` and the standard library. This is the documented rule, enforced.
- **B.** Compute the version from the `ast`-resolved transitive closure of `grader/` files that a check imports. A `checks/_employee_api.py` then regrades only its three lessons. To stay within **ADR 0001**, the registry skips `_`-prefixed modules. That is a filter on the same lookup, not the "second way to find a check" the ADR rejects. A dynamic `importlib.import_module` in a check would escape B, so A's test should also forbid it.
- **C.** `modulefinder`. It relies on a private API, follows the standard library, and adds nothing over B for in-repo files.
- **Fetching.** Fetch `pr.sha` and assert that `rev-parse HEAD` equals it. `checkout` then needs the SHA, and the in-memory test source changes to match.

**Recommendation.**

- A: **Strong**.
- B with the split: **Worth exploring**. It pays off only once lessons are being edited often during workshops; without B, the split alone changes nothing.
- Fetch by SHA: **Strong**.

## 5. Who owns the state-file paths

**Current state.** Commit `a3f09ac` ("Let lessons own lessons.json and the fixtures folder") gave `lessons.lessons_file`/`fixtures` (`lessons.py:65-71`) one owner. The other state files already have one owner each: `participants.csv` and `history.json` in `Roster.__init__` (`roster.py:141-142`), and `results.json` in `Submissions.__init__` (`submissions.py:64`). The one list kept outside Python, `run_and_push.sh:26`, is pinned to those owners by `test_workflows.py:20-27`. The page and Pages deploy name `participants.csv` and `lessons.json` separately (`index.html:251`, `pages.yml:34`); those are the published site's contract, not grader state.

**Options.**

- **A.** Leave it as it is.
- **B.** A `repository.py` holding path constants that `lessons`, `Roster` and `Submissions` read. This is a shallow module: it moves five lines and reverses part of `a3f09ac` unless it delegates to `lessons` for lessons and fixtures.
- **C.** Derive `run_and_push.sh`'s list from Python (`leaderboard.py state-files`). The test already gives the same guarantee.

**Recommendation.** **Not now (A).** If a fourth writer of state files ever appears, add B. It should *delegate* to `lessons` for `lessons.json` and fixtures, not take them over.
