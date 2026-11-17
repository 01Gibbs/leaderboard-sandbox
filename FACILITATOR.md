# Facilitator guide

Everything is done in your browser. You don't need to install anything.

**To make a change:** open the **facilitator page**: the leaderboard's address followed by `facilitator.html` (for example `https://<owner>.github.io/<repository>/facilitator.html`). Find the person (press `/` and type), then press **+1 help**, **+1 stretch**, or **More** for bonus points, taking points away, setting a result, renaming or merging. Each change waits in the **Changes** box, in words. Make as many as you like, for as many people as you like (tick **Select several** to give everyone in a group the same).

**Send** opens GitHub with every waiting change filled in, in one tab: sign in if asked, and press **Submit new issue**, once. About a minute later each change shows **Done** (or **Not done**, with the reason), and the public page updates a minute or two after that. Only the leaderboard's collaborators can make changes (the repository owner adds them under Settings → Collaborators): an issue from anyone else changes nothing. There is no token to make.

**To practise first:** run `python3 facilitator_walkthrough.py` (Windows: `py facilitator_walkthrough.py`) in a copy of this repository. It opens a guided tour of the facilitator page on a practice copy with made-up people, where every change really works and nothing reaches GitHub. For a tour of the leaderboard itself, run `python3 walkthrough.py`.

**If the facilitator page isn't to hand,** the same changes are forms in the Actions tab, one per run: open the repository → **Actions** → pick a *Facilitator:* action on the left → **Run workflow** → fill in the form → **Run workflow**. After about 30 seconds the run's page says what happened: ✅ and what changed, or ❌ *Nothing was changed* and why. For a **person**, type their name as on the leaderboard or their GitHub username; if nobody matches, nothing changes and the run suggests close matches. A run that fails outright means something broke, not that you made a mistake: tell the repository owner.

## I want to…

| …do this | On the facilitator page (pick the person first) | In the Actions tab |
|---|---|---|
| Give points for helping a colleague | **+1 help** (or press `h`) | *Facilitator: Award points*, helped |
| Give points for a stretch task | **+1 stretch** (or press `s`) | *Facilitator: Award points*, stretch |
| Give any other points | **More → Bonus points…** | *Facilitator: Award points*, bonus |
| Give the same to several people | Tick **Select several**, tick them, **+1 help each** | one run per person |
| Take points away | **More → Take some away…** | *Facilitator: Award points*, with a minus sign |
| Show someone's real name instead of their GitHub username | **More → Rename…** | *Facilitator: Rename a person* |
| Fix someone who appears twice | Pick the row to keep, **More → Same person as…** | *Facilitator: Merge duplicate people* |
| Mark an exercise correct that you checked by hand | **Mark correct** next to the exercise | *Facilitator: Mark an exercise* |
| Add someone who hasn't opened a pull request yet | Type their name; **Add** appears when nobody matches | *Facilitator: Add a person* |
| Reverse a mistake | **Undo** next to that change, under *Recent changes* | *Facilitator: Undo last change* (the latest only) |
| Grade new pull requests right now | **Grade now**, then **Run workflow** on GitHub | *Grade submissions* (it also runs by itself once a day) |

Then **Send** once for everything waiting in the Changes box.

## Points
Submitted **10**, correct **30**, each stretch task **+5**, each help **+5**, and bonus points count one for one. The first 3 pull requests on each exercise earn their authors a stretch credit automatically. Equal points share a rank; within it, people with more correct exercises are listed first.

## Good to know
- **New participants appear by themselves** when they open a pull request on an exercise repository. They show under their GitHub profile name or username until you rename them.
- **Merging** keeps the higher value of every column. That means the best result for each exercise and the larger stretch, helped and bonus numbers, so nobody loses points. The kept row remembers both GitHub accounts, so the duplicate doesn't come back.
- **Undo** reverses one change, and only the cells it touched: on the facilitator page, **Undo** next to any change under *Recent changes* (it waits in the Changes box like any other); in the Actions tab, the latest change. Changes made after it are kept (up to the last 100 changes can be undone). Anything changed since, by the grader or by anyone else, is kept; if a cell was changed again since, undo leaves it alone and says so. Each run lists the five most recent changes and who made them.
- **Two facilitators at once is fine.** If two changes are saved at the same moment, both land.
- **Results only go up.** The automatic grader never lowers a result, so it never overwrites your changes. You can't mark an exercise lower than a pull request earned, because the grader would put it straight back. A pull request that is closed without merging stops counting at the next grading run: its early-PR credit passes to the next one opened, and you can then mark its exercise lower. The status it already earned stays until you do, because the grader never lowers a result.
- **Exercise keys** for *Mark an exercise* in the Actions tab are the `key` of each lesson in [`lessons.json`](lessons.json) (on the facilitator page you pick the exercise by name instead).
- **Why a submission isn't *Correct* yet:** open `grader/results.json` and search for the person's GitHub username. Each pull request lists the reasons it passed or failed.
- **❌ Nothing was changed** means the change wasn't made, for example a misspelt name. The run page (or the issue's reply) says why: fix it and send it again.
