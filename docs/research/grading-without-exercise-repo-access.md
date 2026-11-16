# Grading exercise-repository pull requests without access to the exercise repositories

*Research note, 16 November 2026. Audience: project lead.*

## Recommendation

**Primary: a "watcher" workflow in the leaderboard repository (option 1b).** It needs no step from Atul and no access to any exercise repository. It covers `meswright/excersize-1` and every future lesson, because it reads `lessons.json` [1].

- It is one job that runs for up to about 5½ hours. Once a minute it asks GitHub for each lesson's pull requests, using a conditional request [13].
- When something changed, it starts *Grade submissions* with the `workflow_dispatch` trigger that already exists [2].
- It holds only the leaderboard's own `GITHUB_TOKEN`, with `actions: write`. It never checks out or runs participant code.
- `GITHUB_TOKEN` cannot normally start other workflows, but `workflow_dispatch` and `repository_dispatch` are the documented exceptions [18].
- A facilitator starts it at the start of a workshop. A cheap scheduled check also starts it as soon as it sees a new commit. It stops itself after a quiet spell.
- Expected delay: about one to two minutes before grading starts, then the grading time itself.

**Fallback: scheduled polling only (option 1a).** Run a cheap check every 10 minutes, at an odd minute, that starts grading only when something changed. It is equally hands-off, but GitHub promises no timing. Our own sandbox shows scheduled runs starting 1½ to 4 hours late, with about 7 of 17 runs missing [39]. Treat it as "within hours", not "within minutes".

**One-time step for Atul: none for either option.** The only thing he may be asked for later is to re-enable the schedule after 60 quiet days (see 1a). Any of us with write access can do that too [11][19].

If the watcher is ever judged too close to GitHub's terms (see 1b), the smallest Atul-side route that also covers his future repositories is option 3a. In that route Atul creates a free organisation once, moves his exercise repositories and the leaderboard into it, and makes us owners. We then do the rest. It still does not cover `meswright/excersize-1`.

## Comparison

"Latency" means time until grading *starts*. Grading a Java submission takes minutes more. "Exposure" means what a leaked credential could do.

| Option | Who acts | Once or ongoing | Latency | Cost | Exposure | Covers new repos | Covers meswright |
|---|---|---|---|---|---|---|---|
| **1a** Scheduled poll with a cheap gate | Us, in the leaderboard | Once. Re-enable after 60 quiet days | 5 min at best. Observed 1½–4 h, some runs missing [39] | Free on a public repo [15] | `GITHUB_TOKEN` only, scoped to the leaderboard [17] | Yes, through `lessons.json` | Yes |
| **1b** Watcher job (**recommended**) | Us. A facilitator starts it, or the gate does | Once to build. Started per workshop | About 1–2 min while it runs | Free on a public repo [15]. Uses 1 of 20 concurrent jobs [14] | `GITHUB_TOKEN` with `actions: write` on the leaderboard only | Yes | Yes |
| **2** GitHub App + webhook relay | Atul installs the App once. We run a relay server | Once for Atul. The relay is ongoing for us | Seconds | Relay hosting. A server we chose not to run | App key: whatever the App may do on *all* Atul's repos, private ones included | Probably (unconfirmed) [25][26] | No, unless its owner installs the App |
| **2b** App token inside the leaderboard | Atul installs once | Once | No change: still polling | Free | As 2 | Yes | No |
| **3a** Free organisation + organisation secret | Atul once (create, transfer, invite). Us per new repo | Once for Atul. A small step for us per repo | Under a minute | Free [36] | A token that can push to the leaderboard, readable by anyone who can edit an exercise repo's workflows | Only repos created in or moved to the organisation, plus our per-repo step | No |
| **3b** Team organisation + ruleset-required workflow | Atul once. Us once | Once | Under a minute | Paid plan [33][32] | As 3a | Yes, if the ruleset targets all repos | No |
| **3c** Organisation webhook + relay | Atul once. We run a relay | Ongoing relay | Seconds | Relay hosting | Webhook secret and dispatch token on the relay | Yes | No |
| **4** Account-level webhook or workflow | — | — | — | — | — | Does not exist [22] | — |
| **5** Us as collaborators + the current wizard | Atul invites per repo, and also makes and renews the token | Per repo and per token expiry | Under a minute | Free | As 3a, and a token in each repo | No, he must invite again | Only if meswright invites us |
| **6** A signal without a token | — | — | — | — | — | Not possible (see §6) | — |
| **7** Hybrid: 1a/1b plus push where connected | Us. Push only where an owner opted in | As its parts | The better of its parts | Free | As its parts | Yes | Yes (by polling) |
| **8** External scheduler calling `workflow_dispatch` | Atul makes a token, or installs an App on the leaderboard. A third party holds it | Ongoing token renewal | About 1 min | A third-party service | Can start, cancel, re-run or disable the leaderboard's workflows [19] | Yes | Yes |

## 1. Polling from the leaderboard only

### 1a. A scheduled poll with a cheap gate

**What GitHub says.**

- **Interval.** "The shortest interval you can run scheduled workflows is once every 5 minutes" [10].
- **Delays and drops.** The `schedule` event "can be delayed during periods of high loads". "High load times include the start of every hour", and "If the load is sufficiently high enough, some queued jobs may be dropped" [10]. GitHub gives no upper bound.
- **Measured on our sandbox.** From 13 to 16 November, `grade.yml` was on `0 */4 * * *`, so 17 runs were due [39]. Only 10 ran. Each started between 1 h 26 min and 3 h 54 min after the slot before it. An odd minute should do better [10], but we have not measured that.
- **Disabled after 60 days.** "In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days" [10][11]. The docs do not define "activity". So we do not know whether the grader's own deploy-key commits [7] keep the schedule alive. Gaps between workshops can easily pass 60 days. Re-enabling is `gh workflow enable grade.yml` or the Actions tab [11]. The API call needs Actions: write [19], which any of us with write access has.
- **Minutes.** "The use of standard GitHub-hosted runners is free … In public repositories" [15].
- **Rate limit.** "The rate limit for `GITHUB_TOKEN` is 1,000 requests per hour per repository" [12][14]. Listing pull requests on *another* public repository counts against the leaderboard's limit. `grade.py` already does this with `GH_TOKEN: github.token` [3][4].
- **Free conditional requests.** "Making a conditional request does not count against your primary rate limit if a `304` response is returned and the request was made while correctly authorized with an `Authorization` header" [13].

**Making it cheap.** Every grade run today installs Python and three JDKs before it looks at anything [3]. A 10-minute schedule on `grade.yml` itself would therefore spend about a minute of runner time per run for nothing. Runs would also pile up in the `grade` queue behind a long grading run [2].

So add a separate small `check` job, with `contents: read` and `actions: write`:

1. List each lesson's pull requests: `GET /repos/{r}/pulls?state=all&per_page=100`, one or two pages per lesson [4][20].
2. Compare each `(lesson, PR number, head SHA)` with `grader/results.json` on `main`.
3. If any pull request is new, has a new SHA, or has disappeared, call `workflow_dispatch` on `grade.yml` [38].

That is four to eight requests per run, so about 100 an hour at a 5-minute interval. This is a tenth of the limit even without ETags. The gate needs no setup step: `ubuntu-24.04` already has `python3`.

**The gate must ignore grader-error retries** (`passed: null` [4]). Otherwise one broken submission restarts a full grading run every 10 minutes. The daily run keeps retrying those.

**Who / once / exposure.** Only we act, once. The token is the job's own `GITHUB_TOKEN`, scoped to the leaderboard [17]. It expires when the job ends [17].

**Host move.** Nothing to reconnect. The 60-day clock applies to the new repository.

**Verdict.** A good backstop. Not a "within minutes" promise.

### 1b. A watcher job (recommended)

**Idea.** Run the gate from 1a in a loop inside one long job, instead of relying on the scheduler for every check.

- A job on a GitHub-hosted runner may run for 6 hours [14].
- Free accounts get 20 concurrent standard jobs [14]. The watcher uses one.
- In memory, it keeps each lesson's ETag from `GET /repos/{r}/pulls?state=all&sort=updated&direction=desc&per_page=100` [20]. It sends it back as `If-None-Match` every 60 seconds. An unchanged list returns `304` and is free [13].
- When a list changes, it runs the 1a comparison. If there is something to grade, it calls `POST /repos/{leaderboard}/actions/workflows/grade.yml/dispatches` with its `GITHUB_TOKEN` (`actions: write` [19]).
- A `workflow_dispatch` started by `GITHUB_TOKEN` *does* create a run [18]. `grade.yml` already queues runs with `queue: max` [2].

**Starting and stopping.**

- A facilitator presses **Run workflow** at the start of a workshop.
- The 1a schedule also starts the watcher whenever its gate finds work. So the first pull request of the day waits for the scheduler, and later ones do not.
- About 10 minutes before the 6-hour limit, the watcher dispatches itself again and exits. A concurrency group `watch` with `cancel-in-progress: false` and no queue keeps at most one running copy and one waiting copy [9].
- It stops chaining after, say, 2 hours with no pull request changes. It also has a hard cap, such as 12 hours, so a mistake cannot loop for ever.

**Cost.** Free on a public repository [15]. At one request per lesson per minute, it makes 240 requests an hour at most. Most of them are `304` and free [13]. The limit is 1,000 [12].

**Exposure.** `actions: write` on the leaderboard lets a leaked token start, cancel and re-run the leaderboard's workflows, or disable one [19]. It cannot push code. It cannot touch any exercise repository. The job checks out nothing and runs no participant code. The token dies with the job [17]. No stored secret exists.

**Adversarial points.**

- *Terms.* Actions must not be used for "any activity that places a burden on our servers, where that burden is disproportionate to the benefits provided to users". The example given is "don't use Actions as a content delivery network or as part of a serverless application" [16]. A watcher that is time-boxed to workshops and mostly sends free `304` requests serves this project's own testing. It is not a general service. But it is a judgement call. Keep the idle stop and the hard cap, and do not run it all day.
- *Startup depends on someone or the scheduler.* If nobody presses the button and the schedule is late, the first grading can take hours (1a). The facilitator checklist should include "start the watcher".
- *Runner loss.* A hosted runner can fail mid-job. The scheduled gate restarts the watcher on the next change, so nothing is lost. Grading always grades everything outstanding [2].
- *The 60-day disable* hits the schedule, not `workflow_dispatch`. A facilitator can still start the watcher by hand.

**Host move.** Nothing to reconnect. It works the same in Atul's account.

**Covers.** Every lesson in `lessons.json` [1], including `meswright/excersize-1` and future repositories, as long as they are public. Being public is already required [8].

## 2. A GitHub App installed once by Atul

**What it can do.**

- Anyone can install an App on their personal account and choose "All repositories" or "Only select repositories" [25][26].
- The docs do *not* say in plain words that "All repositories" includes repositories created later. They say only that repositories the App itself creates are added [25][26]. This needs a test (Open questions).
- To receive `pull_request` events, the App needs "Pull requests: read", and the event is available to Apps [24].
- **Webhooks need a server.** "You must … specify a webhook URL where GitHub will send the webhook payloads", which is "the address of a web server" [23]. An App webhook cannot start Actions directly. Something must receive it and then call `repository_dispatch` or `workflow_dispatch` on the leaderboard.
- That something is a relay, such as a small hosted function. We decided earlier not to run a server.

**2b. Using an installation token from the leaderboard.**

- `actions/create-github-app-token` can mint a token for another owner's installation (`owner:`). With `repositories` left empty, access covers "all repositories in the provided repository owner's installation" [27].
- The token lasts 1 hour and is revoked when the job ends [27]. An installation gets at least 5,000 requests an hour [12].
- This adds rate limit and private-repository reading. It adds **no trigger**: the leaderboard would still have to poll.
- With write permissions, the App could put the notify workflow and secret into every Atul repository automatically. But then one private key could write to all Atul's repositories, private ones included. That is far too much exposure for a convenience.

**Exposure.** An App's permissions are the same on every repository it is installed on. With "All repositories", even "Pull requests: read" exposes Atul's *private* pull requests if the key leaks. Whoever runs the relay holds that key.

**meswright.** Not covered unless meswright installs the App too.

**Verdict.** Fast, but it needs a server, and a broad one-time grant. Not recommended.

## 3. The organisation route

- **Organisation webhooks** "can subscribe to events that happen in all repositories owned by the organization" [22]. They still need a receiving server (3c).
- **Organisation secrets.**
  - Organisation owners can create them. Access can be "all repositories" or a chosen list [28].
  - On GitHub Free they are not available to *private* repositories [28]. The exercise repositories are public, so that is fine.
  - In an organisation, anyone with write access can create repository secrets [28].
- **Workflows required by rulesets.**
  - Organisation rulesets can require a workflow, and support `pull_request`, `pull_request_target` and `merge_group` [31][35].
  - A public workflow file "can run on any repository in your organization" [31].
  - But organisation-wide rulesets are "for customers on GitHub Team and GitHub Enterprise plans" [32]. Team gained them on 16 June 2025 [33]. Before that, required workflows were Enterprise-only [34].
  - **Free organisations cannot use them.**
  - Also, a required workflow that fails blocks merging [31]. A failed dispatch would then block a participant's merge.
- **Transfer** keeps pull requests, forks, secrets and webhooks, and redirects links. It does not redirect GitHub Pages [37]. The person transferring needs admin rights on the repository and permission to create repositories in the organisation [37].

**3a (free).**

- Atul, once: create a free organisation [36], transfer his exercise repositories (and the leaderboard), and make us owners.
- We, once: create an organisation secret `LEADERBOARD_TOKEN` for all repositories. Its resource owner is the organisation [30].
- We, per new exercise repository: commit `notify-leaderboard.yml`. The wizard already does this, but needs admin [6]. We would be owners, so that is fine.
- Atul's only ongoing duty: create new exercise repositories inside the organisation.
- Exposure is the same as today. The token can change the leaderboard's files, because `repository_dispatch` needs Contents: write [19]. Anyone who can edit an exercise repository's workflows could use it [5].

**3b (Team)** removes the per-repository file, at a monthly per-user price.

**Host move.** Choose the organisation *as* the new host. Then nothing has to move twice.

**meswright** is not covered unless meswright transfers too.

## 4. Account-level options

GitHub supports repository, organisation, Marketplace, Sponsors and App webhooks. "You cannot create webhooks for individual user accounts" [22]. Actions secrets exist at repository, environment and organisation level only [28]. There is no "one workflow for all my repositories" for a personal account. Rulesets across repositories are organisation-only and paid [32]. **Confirmed: no account-level route.**

## 5. Making us collaborators on the exercise repositories

- **Secrets.** "For a personal account repository, you must be a repository collaborator" to create repository secrets [28]. So collaborators *can* set `LEADERBOARD_TOKEN`. Only the owner can manage webhooks and deploy keys [29]. Collaborators can push, so they can commit the workflow file [29]. The wizard's admin check (`setup-pr-trigger.sh:231` [6]) could be relaxed to `push`.
- **The token is the catch.**
  - After the move, the leaderboard belongs to Atul. A fine-grained token "is limited to access resources owned by a single user or organization" [30].
  - Fine-grained tokens do not yet work "to contribute to repositories where the user is an outside or repository collaborator" [30].
  - So **only Atul** can create the fine-grained token for his leaderboard. He must also renew it whenever it expires (30 days by default [30]).
  - A classic token from one of us "can access every repository that you can access" [30]. Placed in an exercise repository's secrets, it would expose all our own repositories. Do not do this.
- **Per repository.** Atul must invite us on every new exercise repository. This does not cover future repositories, or meswright unless meswright invites us.

**Verdict.** The most per-repository and per-expiry work for Atul. Not recommended.

## 6. A signal without a token

- `GITHUB_TOKEN` is "limited to the repository that contains your workflow" [17]. A workflow in an exercise repository cannot call the leaderboard's dispatch endpoints with it.
- `workflow_run`, `check_run` and `check_suite` are events of the workflow's own repository [10]. Nothing in the docs lets repository B's workflow fire on repository A's events [10][18].
- Anything an exercise-repository workflow could publish without a token (a label, a comment, an artifact, a run) is something the leaderboard must still *poll*. The pull-request list it already polls is the cheapest such signal.
- The public Events API is "not built to serve real-time use cases". Its latency "can be anywhere from 30s to 6h" [21].

**Confirmed: no token-free push.** Polling the pull-request list (option 1) is the best token-free route.

## 7. Hybrid

Keep `repository_dispatch` in `grade.yml` [2] for any repository whose owner chooses to install `notify-leaderboard.yml`. Add 1a, and 1b on top. Every repository is covered by polling, and connected ones get seconds-level triggers. Nothing breaks if a token expires: the poll covers it. This is the recommendation, with the push part optional.

## 8. An external scheduler

A third-party cron service calls `workflow_dispatch` every minute. That is more punctual than GitHub's scheduler. It needs Actions: write on the leaderboard [19]. After the move, only Atul can make that fine-grained token [30], or Atul must install an App on the leaderboard. The token sits with a third party and must be renewed. **Use only if 1b is ruled out.**

## What would change in this repository (for 1a + 1b)

- `.github/workflows/watch.yml` (new). Triggers: `workflow_dispatch` (facilitator start, self-renewal). Permissions: `contents: read`, `actions: write`. Concurrency group `watch`. One job that runs `python3 grader/leaderboard.py watch`, with no checkout of participant code. Roughly 40 lines.
- `.github/workflows/grade.yml`:
  - Add a `check` job, run on `schedule` only, for example `cron: '7,17,27,37,47,57 * * * *'`. It runs `leaderboard.py pending`. When work is found, it dispatches `grade.yml` and, if no watcher is running, `watch.yml`.
  - Keep `grade` and `publish` unchanged for `repository_dispatch` and `workflow_dispatch`. Skip them on `schedule`, except for the daily backstop run, which still regrades retries.
  - Update the header comment [2].
- `grader/grade.py` / `grader/leaderboard.py`:
  - A `pending()` function that lists pull requests with the existing `GitHub` source [4] and returns keys whose SHA is new or missing, ignoring `passed: null`.
  - A `watch` command: the ETag loop, the idle stop, the hard cap, and self-dispatch near 5½ hours.
  - Tests use the in-memory source [4].
- `grader/tests/test_workflows.py`: pin `watch.yml`'s permissions, the way the other workflows' security rules are pinned.
- Docs:
  - The README's grading section and the `add-lesson` skill: connecting a repository becomes optional, and they say how to start the watcher.
  - The facilitator checklist: "start the watcher", and "after a long break, run `gh workflow enable grade.yml`".
  - `adding-and-testing-a-lesson.md`'s hand-over gaps 2 and 10 [8] shrink to "optional".
- `grader/setup-pr-trigger.sh` and `grader/exercise-repo/notify-leaderboard.yml`: keep them as the optional push path (option 7).

## Open questions

1. Does the watcher pattern stay within GitHub's Actions terms [16], given a time-boxed run and mostly `304`s? We could ask GitHub Support before relying on it.
2. How late are schedules on an odd minute rather than `:00`? Measure on the sandbox for a week before trusting 1a's numbers [39].
3. Do the leaderboard's own deploy-key commits count as "repository activity" for the 60-day rule [10]? The docs do not say.
4. Does an App installed with "All repositories" pick up repositories created later [25][26]? This only matters for option 2.
5. Does the ETag of `GET /pulls?sort=updated` change on every new head commit? Changing the response body should change it [13], but the watcher should also do a full compare every ~10 minutes in case it does not.
6. If the leaderboard moves into an organisation (3a), can a fine-grained token owned by the organisation be created without approval [30]?

## Sources

1. `lessons.json:1-26` (the four exercise repositories)
2. `.github/workflows/grade.yml:1-26` (triggers, `workflow_dispatch` input `only`, concurrency `queue: max`)
3. `.github/workflows/grade.yml:32-66` (the grade job's read-only token, setup steps, `GH_TOKEN: github.token`)
4. `grader/grade.py:41-61, 99-121` (pull-request listing, retry on `passed=None`, in-memory test source)
5. `grader/exercise-repo/notify-leaderboard.yml:1-29`
6. `grader/setup-pr-trigger.sh:231, 245, 304-306` (admin check, leaderboard name, token resource owner and permission)
7. `grader/run_and_push.sh:26-38` (commits only when something changed)
8. `docs/research/adding-and-testing-a-lesson.md`, "Things a new host should know" and "Gaps found" (exercise repositories must be public; hand-over)
9. `docs/research/architecture-recommendations.md` §3 (concurrency and pending runs)
10. Events that trigger workflows (`schedule`, `workflow_run`, `check_suite`): https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
11. Disabling and enabling a workflow: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
12. Rate limits for the REST API: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
13. Best practices for using the REST API (conditional requests, webhooks over polling): https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
14. Actions limits (6-hour job, 20 concurrent jobs, `GITHUB_TOKEN` 1,000/hour): https://docs.github.com/en/actions/reference/limits
15. GitHub Actions billing (free on public repositories): https://docs.github.com/en/billing/concepts/product-billing/github-actions
16. GitHub Terms for Additional Products and Features, Actions: https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features
17. `GITHUB_TOKEN` (scope, lifetime): https://docs.github.com/en/actions/concepts/security/github_token
18. Triggering a workflow (`GITHUB_TOKEN` events create no runs, except `workflow_dispatch` and `repository_dispatch`): https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow
19. Permissions required for fine-grained personal access tokens (Actions write: workflow `dispatches`, `enable`, `disable`, re-run; Contents write: `POST /repos/{owner}/{repo}/dispatches`): https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens
20. List pull requests (`sort=updated`, `direction`): https://docs.github.com/en/rest/pulls/pulls#list-pull-requests
21. Events API (not real time, 30 s to 6 h): https://docs.github.com/en/rest/activity/events
22. Types of webhooks (no user-account webhooks; organisation webhooks cover all repositories): https://docs.github.com/en/webhooks/types-of-webhooks
23. Using webhooks with GitHub Apps (a URL to a web server is required): https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/using-webhooks-with-github-apps
24. Webhook events and payloads, `pull_request` (availability; "Pull requests" read): https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request
25. Installing a GitHub App from a third party: https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party
26. Reviewing and modifying installed GitHub Apps: https://docs.github.com/en/apps/using-github-apps/reviewing-and-modifying-installed-github-apps
27. `actions/create-github-app-token` README (`owner`, `repositories`, 1-hour token, revoked at job end): https://github.com/actions/create-github-app-token
28. Using secrets in GitHub Actions (who can create them; organisation secrets on Free; forks get no secrets): https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
29. Permission levels for a personal account repository: https://docs.github.com/en/account-and-profile/reference/permission-levels-for-a-personal-account-repository
30. Managing your personal access tokens (single resource owner, collaborator gap, 30-day default, classic breadth): https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
31. Available rules for rulesets, "Require workflows to pass before merging": https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
32. About rulesets (organisation-wide: Team and Enterprise): https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
33. Changelog, 16 June 2025, "Organization rulesets now available for GitHub Team plans": https://github.blog/changelog/2025-06-16-organization-rulesets-now-available-for-github-team-plans/
34. Changelog, 2 August 2023, "Required workflows will move to repository rules" (Enterprise only): https://github.blog/changelog/2023-08-02-github-actions-required-workflows-will-move-to-repository-rules/
35. Changelog, 26 October 2023, ruleset-required workflows support `pull_request_target`: https://github.blog/changelog/2023-10-26-requiring-workflows-with-rulesets-now-supports-the-pull_request_target-trigger
36. GitHub's plans (Free for organisations: unlimited public repositories): https://docs.github.com/en/get-started/learning-about-github/githubs-plans
37. Transferring a repository: https://docs.github.com/en/repositories/creating-and-managing-repositories/transferring-a-repository
38. REST, workflows (create a workflow dispatch event; enable a workflow): https://docs.github.com/en/rest/actions/workflows
39. Measured, 16 November 2026: `gh run list -R 01Gibbs/leaderboard-sandbox --workflow grade.yml --event schedule`. This gave 10 runs between 2026-11-13T21:42Z and 2026-11-16T03:37Z. In that period, `grade.yml` on the sandbox's `main` had `cron: '0 */4 * * *'` (commit `b726af5`, 13 Nov 15:43Z, until `86b6ba4`, 16 Nov 08:33Z), so 17 runs were due. Start times were 03:37, 23:37, 18:07, 11:37, 03:38, 23:28, 17:26, 11:03, 03:54 and 21:42 UTC.
