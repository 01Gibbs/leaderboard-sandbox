# Facilitator guide

Everything is done in your browser. You don't need to install anything.

**To make a change:** open the **facilitator page**: the leaderboard's address followed by `facilitator.html` (for example `https://<owner>.github.io/<repository>/facilitator.html`). Fill in a form and press **Save**. The page lists recent changes by anyone. The public page updates a minute or two later.

Save opens GitHub with the change already filled in, as a new issue: sign in if asked, and press **Submit new issue**. About a minute later the change is made, and the issue is answered with what happened and closed. Only the leaderboard's collaborators can make changes (the repository owner adds them under Settings → Collaborators): an issue from anyone else starts nothing, and nothing changes. There is no token to make.

**To practise first:** run `python3 facilitator_walkthrough.py` (Windows: `py facilitator_walkthrough.py`) in a copy of this repository. It opens a guided tour of the facilitator page on a practice copy with made-up people, where every form really works and nothing reaches GitHub. For a tour of the leaderboard itself, run `python3 walkthrough.py`.

**The same forms are in the Actions tab:** open the repository → **Actions** → pick a *Facilitator:* action on the left → **Run workflow** → fill in the form → **Run workflow**. After about 30 seconds the run shows a ✅ or ❌ with a one-line summary. The page and the Actions tab do exactly the same thing.

When a form asks for a **person**, use either their name as it appears on the leaderboard or their GitHub username. Upper or lower case doesn't matter. If nobody matches, nothing changes and the run suggests close matches.

## I want to…

| …do this | Form (on the page, or *Facilitator:* in Actions) | Fill in |
|---|---|---|
| Give points for helping a colleague | **Facilitator: Award points** | person, *helped*, how many times |
| Give points for a stretch task | **Facilitator: Award points** | person, *stretch*, how many tasks |
| Give any other points | **Facilitator: Award points** | person, *bonus*, how many points |
| Take points away | **Facilitator: Award points** | the same, with a minus sign, e.g. `-1` |
| Show someone's real name instead of their GitHub username | **Facilitator: Rename a person** | GitHub username, real name |
| Fix someone who appears twice | **Facilitator: Merge duplicate people** | the row to keep, the duplicate |
| Mark an exercise correct that you checked by hand | **Facilitator: Mark an exercise** | person, exercise key (see below), *correct* |
| Add someone who hasn't opened a pull request yet | **Facilitator: Add a person** | name, GitHub username if known |
| Reverse a mistake | **Facilitator: Undo last change** | nothing |
| Grade new pull requests right now | **Grade submissions** | nothing (it also runs by itself whenever a pull request changes) |

## Points
Submitted **10**, correct **30**, each stretch task **+5**, each help **+5**, and bonus points count one for one. The first 3 pull requests on each exercise earn their authors a stretch credit automatically. Equal points share a rank; within it, people with more correct exercises are listed first.

## Good to know
- **New participants appear by themselves** when they open a pull request on an exercise repository. They show under their GitHub profile name or username until you rename them.
- **Merging** keeps the higher value of every column. That means the best result for each exercise and the larger stretch, helped and bonus numbers, so nobody loses points. The kept row remembers both GitHub accounts, so the duplicate doesn't come back.
- **Undo** reverses the latest facilitator change, and only the cells that change touched. Run it again to go back one more (up to the last 100 changes). Anything changed since, by the grader or by anyone else, is kept; if a cell was changed again since, undo leaves it alone and says so. Each run lists the five most recent changes and who made them.
- **Two facilitators at once is fine.** If two changes are saved at the same moment, both land.
- **Results only go up.** The automatic grader never lowers a result, so it never overwrites your changes. You can't mark an exercise lower than a pull request earned, because the grader would put it straight back. A pull request that is closed without merging stops counting at the next grading run: its early-PR credit passes to the next one opened, and you can then mark its exercise lower. The status it already earned stays until you do, because the grader never lowers a result.
- **Exercise keys** for *Mark an exercise* are in [`lessons.json`](lessons.json): `fizzbuzz`, `rest_api`, `framework_upgrade`, `container_image`.
- **Why a submission isn't *Correct* yet:** open `grader/results.json` and search for the person's GitHub username. Each pull request lists the reasons it passed or failed.
- **A run with ❌** didn't change anything. Click it to read the reason, fix the form and run it again.
