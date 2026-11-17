# Java Exercise Leaderboard

A public leaderboard for the workshop. Participants submit each exercise as a pull request; the leaderboard grades it and ranks everyone by points. Facilitators grade, add lessons and adjust scores from the facilitator page, with nothing to install and no token.

**New here?** Run `python3 walkthrough.py` (Windows: `py walkthrough.py`) for a five-minute tour in your browser, or `python3 facilitator_walkthrough.py` to try the facilitator page on made-up people.

- **Facilitators:** [FACILITATOR.md](FACILITATOR.md).
- **Setting it up, or taking it over:** [One-time setup](#one-time-setup) below, then [docs/TAKEOVER.md](docs/TAKEOVER.md), with prompts for Claude Code.
- **Changing the code:** [docs/MAINTAINING.md](docs/MAINTAINING.md).

## How it works

```
participant opens a PR ──► Grade submissions (daily, or Grade now) ──► participants.csv ──► public page
                                                                       ▲
facilitator page ── Workshop: Grade now, add a lesson ─────────────────┤
                 └─ People: +1 help, results, names, undo ── Send ─────┘ (one GitHub issue)
```

- **Grading.** *Grade submissions* lists the pull requests on each lesson's repository ([`lessons.json`](lessons.json)), checks each new commit with the grader's own tests, and records the reasons in `grader/results.json`. It runs once a day, and straight away when a facilitator presses **Grade now**. Nothing is needed in the exercise repositories, which must be public.
- **Facilitator changes** wait in the page's Changes box; **Send** opens one GitHub issue with all of them filled in, and only the leaderboard's collaborators' issues are acted on. Every change is logged, so **Undo** reverses any one of them.
- **Lessons** are added from the facilitator page: a new lesson stays hidden until a trial shows its tests work against the exercise, then goes live.
- **The page** (`index.html`, on GitHub Pages) shows `participants.csv`, `lessons.json` and `dashboard.json` (title, workshops, kudos), a minute or two after any change. The grader never lowers a result, so a facilitator's change is never overwritten.

This grew out of [AtulKumarSharma79/Leaderboard](https://github.com/AtulKumarSharma79/Leaderboard), where `participants.csv` was edited by hand; hand edits still work and are kept.

## Points
Submitted **10**, correct **30**, each stretch credit **+5**, each help to a colleague **+5**, plus any bonus. The first **3** pull requests on each exercise earn a stretch credit each (`pr_stretch`, worked out by the grader). Equal points share a rank. The rules live once, in the `RULES` block of `scoring.js`, which the page and the grader both read.

## One-time setup
**The quick way:** run `grader/setup-leaderboard.sh` in a clone, logged in to the GitHub CLI as the repository's owner. It asks before each step and skips what is done. By hand, in the repository's Settings:

1. **Pages** → *Source*: **GitHub Actions**. The page appears at `https://<owner>.github.io/<repository>/`.
2. **A deploy key, so only the workflows save to `main`:** `ssh-keygen -t ed25519 -N "" -C leaderboard-bot -f leaderboard-bot`; **Deploy keys** → add `leaderboard-bot.pub` with **Allow write access**; **Secrets and variables → Actions** → secret `LEADERBOARD_DEPLOY_KEY` = the private key (then delete both files); **Rules → Rulesets** → a branch ruleset for the default branch: restrict deletions, block force pushes, require a pull request (**0** approvals) and the `fast` and `slow` checks (not "up to date"), with **Deploy keys** on the bypass list, **Active**.
3. **Collaborators** → each facilitator with **Write** access. **Issues → Labels** → a `facilitator` label.
4. **Actions → General** → *Require approval for all external contributors*, so only collaborators start workflows.
5. **Actions → Grade submissions → Run workflow**, once (20 to 40 minutes the first time).

The default branch must be called `main`. The page, the scores and the grading reasons are public. Optionally, an exercise repository's owner can run `grader/setup-pr-trigger.sh` so its pull requests are graded within a minute rather than daily.

## Lessons
Each lesson is one entry in `lessons.json`: `key` (the column), `label` (shown), `repo` (where participants open pull requests, public) and `check`, how *Correct* is decided:

| `check` | Correct when | Added |
|---|---|---|
| `none` | a facilitator marks it | from the facilitator page |
| `build` | the submission's Gradle project builds (JDK 17, 21 or 25) | from the facilitator page |
| `tests` | the exercise's tests pass, our pinned copy (so editing them does not help) | from the facilitator page |
| a custom name | a check written for it (`grader/checks/<name>.py`) | through a pull request: ask Claude Code to *"add the lesson in owner/repo to the leaderboard"* |

**From the facilitator page:** Workshop → **Add a lesson**: the repository, its name, how it is checked, and where its tests are (the exercise's own `src/test/`, or another public repository's folder, such as a solutions repository). It stays *checking* until the next grading run tries it: the starter must compile with the pinned tests (and a solutions repository must pass them). Then it goes live and its pull requests are graded. A failed trial says why on the page.

The custom checks today: **FizzBuzz** (the participant's tests must catch 7 planted bugs), **REST API** (calls the running app), **Framework upgrade** (Spring Boot 3.5, `jakarta`, the API unchanged), **Container image** (an approved, pinned, multi-stage, non-root image that runs) and **Replace a library** (no Joda-Time, log4j 1.x or opencsv 2.3; behaviour unchanged).
