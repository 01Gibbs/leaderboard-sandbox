# Taking over the leaderboard

For whoever looks after this repository next. [README.md](../README.md) explains how it works and how to set it up; [FACILITATOR.md](../FACILITATOR.md) is the facilitators' guide. This page covers what those leave out: who does what, moving it to a new home, what it relies on, and prompts to give Claude Code for the routine work.

## Who does what

| Who | Does | How often |
|---|---|---|
| The repository's owner | Settings only the owner can change: Pages, the deploy key and its secret, the ruleset, collaborators. `grader/setup-leaderboard.sh` does them all, asking before each step | Once, and when a facilitator joins |
| Facilitators (collaborators with **Write**) | On the facilitator page: **Grade now**, add or remove a lesson (Workshop); points, results, names, merges and undo (People) | Each workshop |
| A maintainer (anyone with Write, usually with Claude Code) | Lessons with a custom check, changes to checks and the page, through pull requests | Now and then |
| GitHub | Grades new pull requests once a day, saves every change, republishes the page | By itself |

Nothing is ever needed in the exercise repositories.

## What it relies on

- **The exercise repositories are public.** The grader lists and fetches their pull requests without a token.
- **The leaderboard repository is public and its default branch is `main`.** The page reads the scores and the facilitator history from GitHub without signing in, and the workflows save to `main`.
- **The page is at `https://<owner>.github.io/<repository>/`.** That is how the facilitator page knows which repository it belongs to. On any other address (a custom domain), open it as `facilitator.html?repo=<owner>/<repository>`.
- **Gradle projects with a `gradlew` wrapper**, for the `build`, `tests` and custom Java checks. The grader has JDK 17, 21 and 25.
- **The daily grading run stays switched on.** GitHub switches off scheduled runs in a public repository after 60 days with no activity, for example over a long break. To switch it back on: Actions → *Grade submissions* → **Enable workflow**. **Grade now** works either way.

## Moving it to a new home

To move it, for example to the workshop lead's own account:

1. The new owner creates an empty **public** repository, and someone pushes this repository's `main` to it (`git push <new remote> main`). History, scores and lessons come along.
2. The new owner runs `grader/setup-leaderboard.sh` in a clone, logged in to the GitHub CLI as themselves. It publishes the page, adds the deploy key and its secret, the ruleset, the `facilitator` label and the collaborators, then starts the first grading run. Skip its last, optional step (connecting exercise repositories).
3. Share the new facilitator page address, `https://<new owner>.github.io/<repository>/facilitator.html`. Facilitators need to be collaborators on the new repository.

The old copy can stay as a sandbox for trying changes. `grader/tests/e2e_github.py --repo <owner>/<repository> --all` exercises every real workflow there, undoes everything it changed, and when everything passed deletes the issues and runs it caused.

## When something looks wrong

- **A facilitator change shows ❌ on GitHub, but the run is green.** That is a refusal, such as a misspelt name: nothing changed, and the issue or the run's summary says why. A **red** run means something broke. Open the run and read the failing step.
- **A run sits queued for a long time.** GitHub occasionally holds runs before starting them, sometimes for half an hour or more. It will run, and nothing is lost: grading and publishing runs wait their turn rather than being cancelled.
- **A submission is not Correct.** Open `grader/results.json` and search for the participant's GitHub username: each pull request lists the reasons it failed.
- **The page shows old scores.** Each saved change starts *Publish the page*; look at its latest run in Actions.

## Working with Claude Code

`CLAUDE.md` at the top of the repository gives Claude the rules of the house. The `add-lesson` skill gives it the steps for a new lesson. Open Claude Code in a clone of the repository and paste one of these, filling in the parts in angle brackets.

**Getting started**
```text
I'm taking over this leaderboard. Read CLAUDE.md, README.md, FACILITATOR.md and docs/TAKEOVER.md, then run the
fast tests. Tell me in plain words how a pull request becomes points, what a facilitator does, and anything that
looks broken or out of date. Change nothing yet.
```

**Adding a lesson**
```text
Add the lesson in <owner>/<exercise repository> to the leaderboard. The brief is <a link or a file path>.
(If its own tests, a build, or marking by hand is enough, a facilitator can add it from the page instead.)
<There is a reference solution in <owner>/<solution repository> | There is no reference solution.>
Use the add-lesson skill. Propose how it should be graded, and what that will not check, before writing code.
Prove the check with tests that grade a known-good and a known-bad submission, and show me they ran rather than
skipped. Update README.md's list of checks. Open a pull request, and merge it only when both CI checks pass.
After the merge, run Grade submissions and tell me how the existing pull requests were graded.
```

**Fixing how a lesson is graded**
```text
The <lesson key> lesson grades <a pull request link, or a description> as <Correct | not Correct>, but it should
be <the other>. Find out why from grader/results.json and the check in grader/checks/. First write a test in
grader/tests/test_checks.py that reproduces it and fails, then fix the check until it passes. Keep every other
test green. Open a pull request and merge it when CI passes; the next grading run regrades that lesson only.
```

**Adding tests to an existing lesson**
```text
Strengthen the tests for the <lesson key> check. Read its module in grader/checks/ and its tests in
grader/tests/test_checks.py. List the ways a submission could be wrongly passed or failed that no test covers,
then add a test for each, starting from the exercise's starter project. Show me the tests ran. Pull request,
merged when CI passes.
```

**A health check**
```text
Check the leaderboard on GitHub (<owner>/<repository>): workflow runs that failed or are stuck in the last week,
when Grade submissions last succeeded, whether the scheduled run is enabled, and whether the published page
matches main. Fix what is ours to fix through a pull request; tell me about anything only the owner can do.
```
