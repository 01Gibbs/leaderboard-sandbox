# Batched facilitator changes, sent without opening issues

*Research note, 16 November 2026. Audience: project lead. Builds on [facilitator-ui.md](facilitator-ui.md).*

> **Status (16 Nov 2026).** Option B is built (PR #29): no server and no sign-in. Send opens one `Facilitator: Changes` issue in a reused tab, `leaderboard.py batch` applies it, `grader/batches.json` records each row, and `undo <id>` reverses any one change. Option A (a GitHub App with a Cloudflare Worker) was not chosen: everything stays on GitHub Pages.

**Short answer:** A static page cannot get a GitHub token by itself. GitHub's token endpoint needs the client secret for the web flow, and it does not answer browser CORS pre-flights. So "no pasted token, no Submit click" needs **one small server**. The smallest one is a **token exchange**, about 60 lines in a free Cloudflare Worker. It holds only the client secret of a **GitHub App** that is installed on the leaderboard repository alone and asks for one permission, **Actions: write**.

The facilitator presses **Sign in with GitHub** once per day. After that, the page sends each batch as one `workflow_dispatch` call made *as that facilitator*. GitHub itself refuses anyone without write access, so "collaborators only" still holds without code of ours. The dispatch returns the run id, so the page can follow the run with the facilitator's token (5,000 requests/hour) and mark each row done or failed.

`roster.py` records one history entry per row, with an id. A new `undo <id>` reverses just that entry, using the per-cell rule `undo` already has.

**Fallback with no server:** keep issues, but put the whole batch in **one** pre-filled issue, opened in **one reused tab**. That is one Submit click per batch instead of one per change. Status polling is slow in this mode (60 unauthenticated requests/hour per IP).

---

## A. Making a change as a signed-in collaborator

### What GitHub's OAuth endpoints allow

- **PKCE is supported but does not make a public client.** GitHub added PKCE in July 2025 ("S256" only). It also says "GitHub does not distinguish between public and confidential clients" and is "not requiring PKCE for any authentication flow" ([changelog, 2025-07-14](https://github.blog/changelog/2025-07-14-pkce-support-for-oauth-and-github-app-authentication/)). In the web flow's token exchange, `client_secret` is still **Required** ([Authorizing OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps); same for GitHub Apps: [Generating a user access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)).
- **No CORS on the token endpoints.** "CORS pre-flight requests (OPTIONS) are not supported at this time" ([Authorizing OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)). Checked on 16 Nov 2026: `OPTIONS https://github.com/login/oauth/access_token` with an `Origin` header returns 404 and no `Access-Control-*` headers. `api.github.com`, by contrast, sends `access-control-allow-origin: *`. So once the browser has a token, it can call the REST API directly. It just cannot *obtain* the token without a server.
- **Device flow.** "The `client_secret` is not needed for the device flow", and its refresh needs no secret either ([same page](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps)). It still posts to `github.com/login/device/code` and `/login/oauth/access_token`, which have no CORS. It follows RFC 8628, which is meant for devices without a browser, so the user must type an 8-character code at `github.com/login/device`. A *secret-free* CORS proxy could serve it, but the code-typing step is extra work for facilitators.
- GitHub's own guidance for single-page apps: "you cannot secure your client secret … you do have to ship the client secret in the application's code" and "public clients are trivially spoofable" ([Best practices for creating a GitHub App](https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/best-practices-for-creating-a-github-app)). Shipping the secret in `facilitator.html` would still not get past the CORS block, so that route is closed.

### Options compared

| Option | Holds a secret | Facilitator effort | Collaborators only? | Ongoing ops |
|---|---|---|---|---|
| **1. GitHub App + token-exchange Worker** (recommended) | Worker: App client secret | Sign in once/day (8 h token, refreshed via Worker for up to 6 months) | Yes: GitHub enforces write for dispatch | One Worker, one secret to rotate |
| 2. Device flow + secret-free CORS proxy | Nothing | Type a code at github.com once per refresh-token life | Yes, same | One Worker, no secret |
| 3. Relay Worker holding the App **private key**, dispatching as the app | Private key (mints installation tokens) | Still needs sign-in to know who it is | Only if *our* code checks `GET /repos/{o}/{r}/collaborators/{user}/permission` | Most power in the server; reject |
| 4. Issues, one batch per issue (fallback) | Nothing | One Submit click per batch | Yes (existing `author_association` + `issue_form.py` check) | None |

**Option 1 in detail.**

- *Permissions.* `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches` needs repository permission **"Actions": write** and accepts user access tokens (UAT) ([Permissions required for GitHub Apps](https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps)). By contrast, `POST /repos/{o}/{r}/dispatches` (`repository_dispatch`) needs "Contents": write, and creating an issue needs "Issues": write. Actions: write is the narrowest of the three, and it does not grant pushes.
- *Collaborators only.* A user token "can only access resources that the user has access to" and only where the app is installed ([Authenticating on behalf of a user](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-with-a-github-app-on-behalf-of-a-user)). "Write access to the repository is required" to run a workflow ([Manually running a workflow](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)). Anyone may *sign in*, but a non-collaborator's dispatch is refused by GitHub. The workflow should still re-check `github.actor` with `issue_form.permission()` as defence in depth. `github.actor` is "the user that triggered the initial workflow run" ([Contexts](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts)), so history keeps recording the real facilitator.
- *Tokens.* "By default, the user access token expires after 8 hours". The refresh token "expires after 6 months", and refreshing needs the client secret, so it goes through the Worker ([Generating a user access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)). Keep the access token in `sessionStorage`, which is cleared when the tab's session ends ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage)). Keep the refresh token in `localStorage` only if one-click re-sign-in is wanted; otherwise, sign in again each day.
- *The Worker.* It does two things: `/token` exchanges `code` + `code_verifier` for a token, and `/refresh` swaps a refresh token for a new one. It holds `CLIENT_ID` and `CLIENT_SECRET` as encrypted Worker secrets, set with `wrangler secret put` ([Cloudflare secrets](https://developers.cloudflare.com/workers/configuration/secrets/)). It answers CORS only for the Pages origin. The free plan allows "100,000 requests" a day, 10 ms CPU and 50 subrequests per request ([Workers limits](https://developers.cloudflare.com/workers/platform/limits/)), far more than a workshop needs. Azure Functions or Vercel would work the same way. Their free tiers were not checked here.
- *Setup.* The app can be created by script through the manifest flow. That flow "generates the app's … private key (PEM file), client secret, and GitHub App ID", and the person running it owns the registration ([Registering a GitHub App from a manifest](https://docs.github.com/en/apps/sharing-github-apps/registering-a-github-app-from-a-manifest)). Ownership can later be transferred to another account ([Transferring a GitHub App](https://docs.github.com/en/apps/maintaining-github-apps/transferring-ownership-of-a-github-app)).

**Staying on issues (option 4).**

- *No Submit click is impossible.* Creating an issue is `POST /repos/{o}/{r}/issues`, which needs a token ([Issues API](https://docs.github.com/en/rest/issues/issues#create-an-issue)). Unauthenticated requests are only for "fetching public data" ([Rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)). Pre-filled URLs always stop at GitHub's form ([Creating an issue from a URL query](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue#creating-an-issue-from-a-url-query)).
- *One tab.* `window.open(url, 'leaderboard-github')` navigates an existing window of that name instead of opening a new one. But "when `noopener` is used, non-empty target names … are treated like `_blank`", so the page must drop `noopener` and set `handle.opener = null` itself. Each open needs its own user gesture ([MDN window.open](https://developer.mozilla.org/en-US/docs/Web/API/Window/open)). Whether GitHub's headers break name reuse is untested, so check it on the sandbox.
- *One issue per batch.* Add a `changes` textarea to a new `facilitator-batch.yml` form, one change per line. Text fields can be pre-filled. Overlong URLs return `414` (same doc), so cap a batch at about 25 rows.

**GitHub-native alternatives.** Discussions have the same Submit step as issues. Projects (v2) has no event in the Actions trigger list ([Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)). A Codespace takes minutes to start and is a heavyweight way to send a "+1". The Actions "Run workflow" form already exists, but it is one form per change. None of them removes the manual step.

**Recommendation:** option 1, with option 4 kept as the no-sign-in fallback. The existing issue workflow stays, so nothing is lost if the Worker is down.

## B. Batching

**Request.** One dispatch of a new `facilitator-batch.yml` takes two inputs: `batch` (an id) and `changes` (a JSON array). `workflow_dispatch` allows up to 25 inputs, and the inputs payload can be up to 65,535 characters ([Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)). That leaves plenty of room. The response includes `workflow_run_id`, `run_url` and `html_url` ([Workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)).

```json
{"batch": "b-20261116-1042-7f3a",
 "changes": "[[\"award\",\"Asha\",\"helped\",\"1\"],[\"award\",\"Ben\",\"helped\",\"1\"],[\"rename\",\"benokafor-gh\",\"Ben Okafor\"],[\"undo\",\"b-20261116-1031-c2e9.0\"]]"}
```

Each row is exactly the args array that `leaderboard.py --args-json` takes today, so `FORMS` and the per-change workflows stay as they are.

**Applying.** Add a new command, `leaderboard.py batch <id> <json>`. It runs inside a single `run_and_push.sh` call, so the batch is one commit and one Pages deploy. It applies the rows in order, each through the existing `Roster` method. A row that raises `ActionError` is recorded as failed, and the remaining rows still run. Each row is its own change, as in the compensating-transaction view below, not all-or-nothing. If the push loses a race, `run_and_push.sh` already resets to the new `main` and re-runs the whole batch. Row ids are deterministic (`<batch>.<index>`), so a retry writes the same ids.

**Reporting.** Write `grader/batches.json`, which keeps the last 50 batches, in the same commit:

```json
{"id": "b-20261116-1042-7f3a", "by": "asharao", "at": "…", "rows": [
  {"i": 0, "ok": true,  "entry": "b-20261116-1042-7f3a.0", "text": "Gave 1 help to Asha Rao (helped: 1 -> 2)"},
  {"i": 2, "ok": false, "error": "Nobody called \"benokafor-gh\" is on the leaderboard. Did you mean 'benokafor'?"}]}
```

The step summary lists the same rows. The run concludes **success** even with failed rows, matching today's rule that a refused change is "an answer, not a fault".

**History.** Keep one entry per successful row, with three new fields: `id`, `batch` and `row`, plus `undone_by` once the entry is undone. Old entries without an id get `legacy-<index>` when read. `HISTORY_LIMIT` should rise from 100 to about 500, because per-row entries fill it faster.

## C. Per-row (selective) undo

**Prior art.**

- `git revert` reverts "the changes that the related patches introduce" for given commits, any commit rather than only the latest, and records new commits. If later commits touched the same lines, it stops with a conflict to resolve or `--skip` ([git-revert](https://git-scm.com/docs/git-revert)).
- Prakash & Knister defined selective undo for multi-user editors: undo a chosen earlier operation, and detect when later operations by others conflict with it ([A framework for undoing actions in collaborative systems, ACM TOCHI 1(4), 1994](https://web.eecs.umich.edu/~aprakash/papers/undo-tochi94.pdf)).
- The compensating-transaction pattern warns that simply restoring the original state "can overwrite changes from other concurrent application instances". It says to design each compensation step as an idempotent command ([Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction)).
- Google Docs only restores a *whole* earlier version ([Google Docs help](https://support.google.com/docs/answer/190843)). That is the model to avoid here.

**Proposal: `undo <entry id>`.** It is today's `undo()` body, applied to the entry with that id instead of `history.pop()`:

1. Find the entry. Refuse if it is missing (aged out), and refuse if `undone_by` is set: "Already undone by b-….3 at 10:44". This makes undo idempotent.
2. For each cell the entry changed, set it back only if the current value still equals what the entry wrote. Otherwise report it as kept: "Ben's name was changed again since, so it stays Ben O." Skip generated columns (`rules.GENERATED`, e.g. `pr_stretch`), because `_save` recomputes them.
3. Mark the entry `undone_by: <this row's id>`. Record the undo as its own entry, so it shows in history and is itself visible, but it is not undoable. To redo, make the change again.
4. Later entries are untouched. Their `before`/`after` snapshots stay valid, because the per-cell rule compares against the *current* value.
5. Graded results still win: `_save` raises statuses to the best PR result after any undo. Undoing a "Mark correct" on an exercise the grader also earned therefore changes nothing, and the result says so, as `mark` already notes.

`undo` with no id keeps working: it undoes the newest entry that has not been undone.

**Edge cases.**

| Case | Behaviour |
|---|---|
| Undo an **add** after the person was awarded or renamed | Refuse: "Asha has changed since being added (helped 0→1). Undo those rows first." Removing the row would silently drop later points. Today's `undo` removes it anyway, which is fine only because it is always the latest entry. |
| Undo an add whose login now has graded PRs | Refuse, or warn: `_save` would re-add the row straight away. |
| Undo a **merge** | Re-add the dropped rows and revert the kept row's cells, each only where unchanged. Refuse if any dropped row's login is now on a row other than the kept one, which would create duplicate logins. Report kept cells, e.g. helped stays 3 because a help was given after the merge. |
| Undo a row **twice** (double click, two facilitators) | The second is refused by `undone_by`. The page disables the button once it has been sent. |
| Undo a row whose cells all changed since | Succeeds with nothing changed and "Kept: …" lines. The page shows it as done-with-notes, not failed. |

## D. Status per row

**With the user token (option 1).** Poll `GET /repos/{o}/{r}/actions/runs/{workflow_run_id}` every 5 s until `status: completed`. Then read `grader/batches.json` through the contents API and match it by batch id. Authenticated, that is 5,000 requests/hour per user. Conditional requests answered `304` "do not count" when they are made "while correctly authorized" ([REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#use-conditional-requests)). The contents API serves fresh `main`, while the Pages copy and `raw.githubusercontent.com` were served with `cache-control: max-age=600` and `300` respectively (observed 16 Nov 2026). A run that fails outright (`conclusion: failure`) marks every row in it failed, with a link to `html_url`.

**Without a token (fallback).** Unauthenticated requests are limited to "60 requests per hour" and "associated with the originating IP address" ([Rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)). Facilitators on one venue network share that budget, so poll `batches.json` at most once a minute, and only while something is pending.

**UX.** Rows move through these states: *queued* (on the page, not yet sent), *sending*, *pending* (run in progress), then either ✓ *done* or ✗ *failed*. A done row shows ✓ with its sentence for about 5 s, then fades out. Its **Undo** moves to a "Recent" list underneath, which holds the last 10 done rows until dismissed. That follows the earlier note's reasoning: Material advises against auto-dismissing undo on the web unless feedback is also shown inline ([Material 3 Snackbar](https://m3.material.io/components/snackbar/guidelines)), and undo is preferred over confirmation for routine actions ([NN/g](https://www.nngroup.com/articles/confirmation-dialog/)). Failed rows stay in the box with the reason, plus **Edit** and **Remove**. All status text goes to one `aria-live="polite"` region.

## E. Design

**The changes box.**

```
┌ Changes to send ───────────────────── Signed in as @asharao ┐
│ +1 help → Ben Okafor                                 [×]    │
│ +1 help → Chen Li                                    [×]    │
│ Rename benokafor-gh → Ben Okafor                     [×]    │
│                                     [Send 3 changes]        │
├ Sending ────────────────────────────────────────────────────┤
│ ◌ +1 help → Asha Rao            pending                     │
│ ✓ +1 stretch → Dev Patel        done (fading)               │
│ ✗ Rename priya → Priya S        Nobody called "priya"…      │
│                                 [Edit] [Remove]             │
├ Recent (undo) ──────────────────────────────────────────────┤
│ ✓ 10:42 +1 help → Ben Okafor    [Undo]                      │
│ ✓ 10:41 Added Chen Li           [Undo]                      │
└─────────────────────────────────────────────────────────────┘
```

Queued rows live in `localStorage`, so a reload loses nothing. Not signed in: the button reads **Send on GitHub (1 issue)**, which is option 4.

**Workflow changes.**

- New `facilitator-batch.yml`. It runs on `workflow_dispatch` (inputs `batch`, `changes`), and on `issues: opened` with title `Facilitator: Batch` for the fallback. It re-checks permission and calls a batch variant of `facilitator-action.yml`.
- `changes-from-issues.yml` learns the batch form.
- `issue_form.py` parses the `changes` lines.
- Single-change forms stay as they are.

**Tests.**

- *Roster unit tests:* `undo(id)` reverses only that entry. It keeps cells changed since and reports them. It refuses a second undo, an aged-out id, and an add with later changes. Undoing a merge restores the dropped rows. Graded statuses survive undo. Batch ids are stable across a re-run.
- *Batch command tests:* a failing row does not stop the others, and `batches.json` matches the history entries.
- *Issue form tests:* batch lines parse, and malformed lines become failed rows.
- *Browser journeys (practice server):* queue 3 → send → rows go pending → done → fade. A failed row stays with its reason. Undo on a recent row lands. A reload keeps the queue. Signed-out mode builds one issue URL under the length cap.
- *Worker:* a unit test of the exchange with a mocked GitHub, and a refusal for a wrong `Origin`.

**Effort (rough).**

| Work | Days |
|---|---|
| Roster `undo <id>`, history ids, batch command, tests | 1.5 |
| Workflows and issue form | 0.5 |
| Worker, plus setup steps (manifest flow, `wrangler`) in `setup-leaderboard.sh` | 1 |
| Page: changes box, sign-in, polling, browser tests | 2 |
| **Total** | **≈ 5** |

**Risks.**

- *Concurrent facilitators.* `run_and_push.sh` rebases by re-running, and the per-cell undo rule never overwrites a newer value. Two batches touching one person both land, in push order.
- *Undo after someone else's change.* The cell is kept and reported, never clobbered, and the page shows the "Kept" lines.
- *Actions: write is broad.* It also lets the token cancel, re-run or disable workflows. Collaborators can already do all of that, so it grants nothing new.
- *Secret rotation.* Regenerate the client secret in the app settings, then run `wrangler secret put CLIENT_SECRET`. Facilitators' existing tokens keep working until they expire.
- *Worker outage.* The page falls back to option 4 automatically.

**Hand-over to Atul's account.**

1. Run the setup in Atul's account: create the GitHub App from the manifest, or transfer the existing one.
2. Install the app on his leaderboard repository only.
3. Deploy the Worker on his free Cloudflare account, with `CLIENT_ID`, `CLIENT_SECRET` and `ALLOWED_ORIGIN` set to his Pages URL.
4. Set the app's callback URL to his `facilitator.html`.
5. Put the client id and Worker URL in the page's config (not secret).
6. Facilitators stay as repository collaborators with write access. Nothing else per person.
