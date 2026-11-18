# Waiting less for the `slow` check

*Research note, 18 November 2026. Audience: maintainers. About `.github/workflows/test.yml`.*

> **Status (18 Nov 2026).** Built as recommended (A and B) in `.github/workflows/test.yml`.

**Short answer:** the `slow` job takes 13 to 19 minutes, and two things cause it. Neither is the browser tests themselves.

1. **`playwright install --with-deps chromium` waits on Ubuntu's package mirror.** In run 44332418555 (18 Nov), apt fetched 32.1 MB "in 6min 48s (78.6 kB/s)": nine new packages, mostly fonts, and four upgrades. The Chromium download took about 15 seconds. The runner image already has Google Chrome, installed by apt with its libraries, and Playwright can launch it with `channel="chrome"`. So the step can go.
2. **The test step is serial, and one class takes most of it.** In the same run, the 9 min 13 s step broke down as: `test_checks.GradleCheckTests` 355 s (19 Spring Boot builds), `ContainerCheckTests` 48 s, `test_workflows` 56 s, `test_facilitator_browser` 51 s, everything else about 40 s. Two parallel jobs, one with the Gradle class and one with the rest, finish in about 6 minutes, and the longer one sets the time.

A final job named `slow`, with `needs:` on both and `if: always()`, keeps the required check without touching the ruleset.

Timings come from `gh run view 44332418555 --log` on 01Gibbs/leaderboard-sandbox, matching each test's "ok" line timestamp against the line before it.

---

## 1. Is Google Chrome on the runner, and can Playwright use it?

- **It is preinstalled.** The Ubuntu 24.04 image readme lists, under "Browsers and Drivers": "Google Chrome 157.0.8103.50", "ChromeDriver 157.0.8103.50", "Chromium 157.0.8103.0" (image 20261111.370.1; [Ubuntu2404-Readme.md](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md), section *Browsers and Drivers*).
- **Its system libraries come with it.** The image's build script installs the official `.deb` with apt, which resolves the package's dependencies: `CHROME_DEB_URL="https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"` … `apt-get install "$chrome_deb_path" -f` ([install-google-chrome.sh](https://github.com/actions/runner-images/blob/main/images/ubuntu/scripts/build/install-google-chrome.sh), lines under "Download and install Google Chrome").
- **Playwright launches it with no `playwright install`.** Playwright "can operate against the branded Google Chrome and Microsoft Edge browsers available on the machine (note that Playwright doesn't install them by default)". The Python form is `p.chromium.launch(channel=...)` ([Browsers → Google Chrome & Microsoft Edge](https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge)). On Linux, Playwright looks for the `chrome` channel at `/opt/google/chrome/chrome` ([registry/index.ts](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/registry/index.ts), line 600), which is where the `.deb` installs. `--with-deps` is only needed for Playwright's own browser builds ([Browsers → Install system dependencies](https://playwright.dev/python/docs/browsers#install-system-dependencies)).
- **Versions.** `channel` is one of the launch options listed "since: v1.8" ([class-browsertype.md, `BrowserType.launch` options](https://github.com/microsoft/playwright/blob/main/docs/src/api/class-browsertype.md); [`launch(channel=…)`](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-option-channel)). Any version we would pin supports it. "The current Playwright version will support Stable and Beta channels" ([same Browsers section](https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge)). Playwright 1.65 "was also tested against … Google Chrome 157" ([Python release notes, Version 1.65](https://playwright.dev/python/docs/release-notes)), the version the image carries today.

**Caveats**

- **Drift.** The image changes under us: "We typically deploy weekly updates to the software on the runner images" ([runner-images README, *Image Releases → Cadence*](https://github.com/actions/runner-images#image-releases)). Our pin (`playwright==1.65.2`) guarantees only the Chrome stable that was current when 1.65 was released. If Chrome gets ahead of a stale pin and launching breaks, the fix is to bump the pin. Pinned Chromium never drifts, which is why Playwright recommends it by default ([Browsers → *When to use Google Chrome & Microsoft Edge and when not to?*](https://playwright.dev/python/docs/browsers#when-to-use-google-chrome--microsoft-edge-and-when-not-to)).
- **Headless mode differs.** "Google Chrome and Microsoft Edge have switched to a new headless mode … This differs from chromium headless shell that is used in Playwright by default when running headless, so expect different behavior in some cases" ([same section, second warning](https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge)). Our journeys click and read text and take no screenshots, so this should not matter, but run them once before switching.
- **Locally nothing changes.** Read the channel from an environment variable that only CI sets. A laptop with no Chrome keeps using `playwright install chromium`.

## 2. If not Chrome: caching Playwright's browsers

Playwright advises against it: "Caching browser binaries is not recommended, since the amount of time it takes to restore the cache is comparable to the time it takes to download the binaries. Especially under Linux, operating system dependencies need to be installed, which are not cacheable." If you cache anyway, cache `~/.cache/ms-playwright` "against a hash of the Playwright version" ([CI → *Caching browsers*](https://playwright.dev/python/docs/ci#caching-browsers); path from [Browsers → *Managing browser binaries*](https://playwright.dev/python/docs/browsers#managing-browser-binaries)). Caches unused for a week are evicted ([actions/cache README, *Cache Limits*](https://github.com/actions/cache#cache-limits)).

For us a cache would not help. The slow part is apt (`install-deps`), and that still runs on every run.

## 3. Splitting `slow` and keeping a required check named `slow`

- **Check name is the job name.** For workflows, a required status check's "name format is `<job name>`", and "Required status checks do not take workflow, matrix, or event trigger types into account" ([Troubleshooting rules → *Troubleshooting required status checks*](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/troubleshooting-rules)). The job name is `jobs.<job_id>.name`, or the id when no name is set ([Using jobs → *Setting a name for a job*](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs#setting-a-name-for-a-job)). Keep job names unique across all workflows: "Using the same job name in multiple workflows can cause ambiguous status check results and block pull requests from being merged" ([About protected branches, tip](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#about-branch-protection-rules)). So the shards need names other than `slow`, and the gate takes `slow`.
- **A skipped job passes.** "A job that is skipped will report its status as 'Success'. It will not prevent a pull request from merging, even if it is a required check" ([Control jobs with conditions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions)). Required checks pass on "`success`, `skipped`, and `neutral`" ([Troubleshooting required status checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks#required-check-needs-to-succeed-against-the-latest-commit-sha)).
- **That is why a plain `needs:` gate is unsafe.** "If a job fails or is skipped, all jobs that need it are skipped unless the jobs use a conditional expression that causes the job to continue … use the `always()` conditional expression in `jobs.<job_id>.if`" ([Using jobs → *Defining prerequisite jobs*](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs#defining-prerequisite-jobs)). GitHub's table puts it plainly: "A job depends on a failed job | The dependent job is skipped and may not block merging | Use `always()` with `needs` for required checks that depend on other jobs" ([Troubleshooting required status checks → *Handling skipped but required checks*](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks#handling-skipped-but-required-checks)). Without `always()`, a failed shard would turn the gate green.
- **`always()` rather than `!cancelled()`.** GitHub's expressions page generally prefers `!cancelled()` ([Expressions → *always*](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#always)). A gate is the exception: it must run after a cancelled shard and fail, and not end up skipped, because a skipped gate counts as a pass. The gate checks out no code and runs one shell test, so the hang that warning describes cannot happen.
- **Reading the results.** `needs.<job_id>.result` is "`success`, `failure`, `cancelled`, or `skipped`" ([Contexts → `needs` context](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#needs-context)). `needs.*.result` uses the documented object-filter syntax ([Expressions → *Object filters*](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#object-filters)).

## 4. Choosing tests with `unittest`

`python -m unittest test_module.TestClass` runs one class. `-k` keeps tests whose fully qualified name matches a substring or `fnmatch` pattern, and can be given more than once. `discover -p` changes the file pattern (`test*.py` by default). There is no "exclude" option ([unittest → *Command-line interface*](https://docs.python.org/3/library/unittest.html#command-line-interface), [*Test discovery*](https://docs.python.org/3/library/unittest.html#test-discovery)). Checked locally: `cd grader/tests && GRADER_FAST=1 python3 -m unittest -v test_checks.GradleCheckTests` finds all 19 tests (skipped, because of `GRADER_FAST`). Since nothing can exclude a class, the other shard needs one `skipIf` on `GradleCheckTests`.

---

## Recommendation

Make two changes in one pull request. Each works without the other.

**A. Use the runner's Chrome; drop `--with-deps`.** This saves 0.5 to 8 minutes and removes the variance. In `test_facilitator_browser.py`:

```python
cls.browser = cls.pw.chromium.launch(channel=os.environ.get('GRADER_BROWSER_CHANNEL'))  # CI: 'chrome'
```

In the workflow, replace the install step with `python3 -m pip install --quiet playwright==1.65.2`, and set `GRADER_BROWSER_CHANNEL: chrome` on the test step.

**B. Run the Gradle class beside everything else, gated by a job named `slow`.** With a matrix, the setup steps exist once. In `tiers.py` (applied to `GradleCheckTests`):

```python
in_gradle_shard = unittest.skipIf(os.environ.get('GRADER_SKIP_GRADLE'), 'runs in the slow (gradle) shard')
```

```yaml
  slow-shard:
    name: slow (${{ matrix.shard }})
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    strategy:
      fail-fast: false
      matrix:
        include:
          - shard: gradle
            run: cd grader/tests && python3 -m unittest -v test_checks.GradleCheckTests
          - shard: rest
            skip_gradle: '1'
            run: python3 -m unittest discover -v grader/tests
    steps:
      # checkout, setup-python, setup-node, setup-java: unchanged
      - name: Install Playwright (drives the runner's Google Chrome)
        run: python3 -m pip install --quiet playwright==1.65.2
      # sandbox user steps: unchanged
      - name: Run this shard's tests
        env:
          GRADER_SANDBOX_USER: grader-sandbox
          GRADER_CACHE: /tmp/grader-cache
          GRADER_BROWSER_CHANNEL: chrome
          GRADER_SKIP_GRADLE: ${{ matrix.skip_gradle }}
        run: ${{ matrix.run }}

  slow:  # the required check: passes only when every shard passed
    needs: slow-shard
    if: always()
    runs-on: ubuntu-24.04
    timeout-minutes: 2
    steps:
      - if: contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled') || contains(needs.*.result, 'skipped')
        run: exit 1
      - run: echo 'every slow shard passed'
```

Why it fails safe: if `GradleCheckTests` is renamed, the `gradle` shard fails on import instead of silently running nothing, so the skip in the `rest` shard cannot hide tests. The ruleset still requires `fast` and `slow` and needs no change. The shard checks (`slow (gradle)`, `slow (rest)`) are not required.

**Expected saving.** Now: about 20 s setup, 0.5 to 8 min install, about 9 to 12 min tests, so 13 to 19 min. After A: 10 to 12 min, and steady. After A and B: the `gradle` shard takes about 30 s setup plus about 6 to 7 min, the `rest` shard about 30 s plus 3.5 min, and the gate adds a few seconds and a runner pickup. That is **about 7 to 8 minutes, roughly half the best case today and under half the worst**. It costs one extra runner for about 4 minutes per run. Splitting further would not help: the 19 Gradle builds take about 6 minutes on their own. Making them shorter (a shared Gradle cache, for example) is a separate question.

**Same pull request, per CLAUDE.md:** describe the `slow` gate and shards in README.md's "For maintainers" section and in the workflow's header comment. Mention `GRADER_BROWSER_CHANNEL` in the browser test's module docstring.
