# Facilitator guide

Everything happens in your browser, on the **facilitator page**: the leaderboard's address followed by `facilitator.html` (for example `https://<owner>.github.io/<repository>/facilitator.html`). You need a GitHub account with **Write** access to the leaderboard (the owner adds you under Settings → Collaborators). Nothing to install, no token.

**To practise first:** `python3 facilitator_walkthrough.py` (Windows: `py facilitator_walkthrough.py`) opens a guided tour of the page on made-up people, where everything really works and nothing reaches GitHub.

## Workshop: the everyday tab
- **Grade now.** New pull requests are graded once a day by themselves. After a burst of them, press **Grade now**: GitHub opens *Grade submissions*; press **Run workflow**, then the green **Run workflow**. About 5 to 20 minutes later the scores follow. The page says when grading last ran.
- **The lessons.** Every exercise, and its state: **Live**; **Checking** (a new lesson, tried at the next grading run); or **Failed its trial**, with the reason (open **Full reason**). A failed lesson is tried again a day later, or now with **Try again**.
- **Add a lesson.** Open **Add a lesson** and give: the exercise's public repository (paste its GitHub address); the name to show (the column name is made from it); how it is checked (**tests**, **build**, or **by hand**). A tests lesson uses the exercise's own `src/test/`; only if its tests are kept elsewhere, such as a solutions repository, paste that folder's GitHub address under **Tests from another repository (optional)**. The page checks what it can, then **Add to changes**, then **Send**. The new lesson stays *Checking* until a grading run shows its tests compile against the exercise, then goes **Live**: its column appears and its pull requests are graded.
- **Remove a lesson** added by mistake: **Remove** next to it. Its results are kept, so adding it again brings them back.

## People: adjusting someone
Find the person (press `/` and type a name or GitHub username), then:

| To… | Press |
|---|---|
| Give points for helping a colleague | **+1 help** (or `h`) |
| Give points for a stretch task | **+1 stretch** (or `s`) |
| Give bonus points | **More → Bonus points…** (how many points) |
| Take away a help, a stretch task or bonus points | **More → Take some away…** (one help or stretch at a time; bonus asks how many points) |
| Give the same to a group | Tick **Select several**, tick them, **+1 help each** |
| Mark an exercise you checked by hand | **Mark correct** next to it |
| Show a real name instead of a GitHub username | **More → Rename…** |
| Fix someone who appears twice | Pick the row to keep, **More → Same person as…** |
| Add someone with no pull request yet | Type their name; **Add** appears when nobody matches |
| Reverse a mistake | **Undo** next to it, under *Recent changes* |

## Send
Every change from either tab waits in the **Changes** box, in words. **Send** opens GitHub with all of them filled in: press **Submit new issue**, once. About a minute later each shows **Done**, or **Not done** with the reason (a misspelt name, say: fix it and send again). The public page follows a minute or two later. An issue from anyone who isn't a collaborator changes nothing.

## Good to know
- **New participants appear by themselves** when they open a pull request, under their GitHub name until you rename them.
- **Results only go up.** The grader never lowers a result, so it never overwrites your changes.
- **Merging** keeps the higher value of every column, so nobody loses points, and remembers both GitHub accounts.
- **Undo** reverses only the cells that change touched; anything changed since is kept.
- **Two facilitators at once is fine:** both changes land.
- **Why isn't a submission *Correct*?** Open `grader/results.json` and search for their GitHub username: each pull request lists its reasons.
- **Points:** submitted 10, correct 30, each stretch +5, each help +5, bonus one for one. Helps and stretch tasks are counted one at a time: +1 per press.
- **Stretch** comes two ways: automatically, for the first 3 pull requests on each exercise; and by hand (**+1 stretch**), for a stretch task you saw done.
- **No facilitator page to hand?** Changes to people, one at a time, are forms in the repository's **Actions** tab (*Facilitator: …* → **Run workflow**). Lessons are added and removed on the page only.
