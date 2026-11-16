# A person-centred facilitator page

*Research note, 16 November 2026. Audience: project lead and facilitators.*

**Short answer:** Rebuild `facilitator.html` as **a roster on the left and one person on the right**. A filter box narrows the roster as you type. Picking a person shows their points, exercises and counts, with **+1 help** and **+1 stretch** as one-click buttons, a **Mark correct** link on each unfinished exercise, and the rarer actions (bonus, take away, rename, merge) in a **More** menu. Ticking several people turns the same buttons into a bulk award. Add happens where a search finds nobody, and merge starts from the person you are looking at. Each action ends in an **Open on GitHub** button that opens the pre-filled issue form. A tray then follows the change until it lands, and offers **Undo** only while that change is still the latest one. All the products below use the same shape: select the subject, see its state, then choose a verb. The workflows, `FORMS` and ADR 0002 stay as they are. Only the page around them changes.

---

## 1. Facilitator journeys, most frequent first

The code and docs suggest these journeys. Frequencies are estimates for a 10–40 person session. The only evidence is `grader/history.json`, which today holds 6 renames and 1 award.

| # | Journey | Today | Why this frequency |
|---|---|---|---|
| 1 | **Someone helped a colleague → give them a help** | Award, *helped*, 1 | The only thing facilitators observe live that no workflow can see (`FACILITATOR.md`, "I want to…"). Several times per session. |
| 2 | **A person shows as their GitHub login → rename** | Rename | Everyone who opens a PR is added under their GitHub name until renamed ("Good to know"). Once per participant. It is 6 of the 7 history entries so far. |
| 3 | **Someone finished a stretch task → +1 stretch** | Award, *stretch* | Often, though the first 3 PRs per exercise already earn it automatically (`RULES.earlyBonus`). |
| 4 | **Who has what right now?** | Leaderboard tab, or `grader/results.json` | Needed before most of the journeys above, to check the right person and the current state. Today the page shows no state. |
| 5 | **End of session: points for several people** | Award form, once per person | One run of the journey per person. ClassDojo-style multi-select (§2) is the comparable pattern. |
| 6 | **I made a mistake → undo, or award -1** | Undo, or Award with a minus | After about 1 in 10 changes. Undo reverses the latest change *by anyone* (`facilitator-forms.js`). |
| 7 | **Checked an exercise by hand → mark correct** | Mark | Rare. All four lessons have automatic checks (`lessons.json`), so marking is for what a check can't judge. |
| 8 | **Same person twice → merge** | Merge | Rare. Happens when someone is added by name and then opens a PR under an unknown login. |
| 9 | **Someone has no PR yet → add** | Add | Rare. People are added automatically when they open a PR. |

In every journey except undo, a person comes first. Journeys 1–3 and 6 are one person and one verb. Today each of them means retyping a name into one of four separate "Person" fields.

## 2. How comparable products do it

**Classroom points (ClassDojo).** You pick students on the class grid, then the award. For several students: "Select multiple" at the bottom, choose students or "Select All", then "Give feedback" and the skill ([Award Multiple Students at Once](https://help.classdojo.com/hc/en-us/articles/202027979-Award-Multiple-Students-at-Once)). Undo reverses only the most recent point, from a reverse arrow in the banner that appears after awarding. Older points are removed through Reports ([How to Undo a Point](https://help.classdojo.com/hc/en-us/articles/209619243-How-to-Undo-a-Point)). That is the same "undo reverses the latest" rule this repo has.

**Gradebooks.** In Google Classroom, on the Student work page, you "click a student's name" on the left, and "Next to the student's name, enter the grade. The grade saves automatically" ([Grade and return an assignment](https://support.google.com/edu/classroom/answer/6020294)). Canvas SpeedGrader uses a student dropdown with previous/next arrows and *j*/*k* shortcuts. That comes from community answers, not the official guide ([Community thread](https://community.instructure.com/en/discussion/614850/speedgrader-moving-between-students)), so treat it as weaker evidence.

**Record pages with actions.** The Salesforce Lightning page header sits "at the top of every record home". It shows the record title and a few key fields, with a few actions as buttons and the rest under a "More Actions" dropdown ([SLDS page headers, archived 2.1.4](https://archive-2_1_4.lightningdesignsystem.com/components/page-headers)). In Stripe, you "Click a customer's name to see more details, including subscriptions, payments…", and pressing `?` lists keyboard shortcuts ([Stripe Web Dashboard](https://docs.stripe.com/dashboard/basics)). GitHub's own Collaborators page says to "start typing the name of the … person you'd like to find", then use the **Role** dropdown or **Remove** next to that person ([Managing teams and people](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-teams-and-people-with-access-to-your-repository)).

**Design-system guidance.**

- *Person picker.* "A combobox is an input widget that has an associated popup." DOM focus stays on the input, and `aria-activedescendant` points at the highlighted option. Down Arrow moves, Enter commits, Escape closes ([WAI-ARIA APG combobox](https://www.w3.org/WAI/ARIA/apg/patterns/combobox/)).
- *Select vs action menu.* Atlassian keeps **Select** for choosing items and **Dropdown menu** for "a list of immediate actions". It recommends ordering options by usefulness, "such as most commonly selected" ([Atlassian Select usage](https://atlassian.design/components/select/usage)).
- *Overflow menus.* Hidden menus may go unnoticed, so give them a visible cue such as an ellipsis or arrow. Every action in one should also be reachable another way. Disable irrelevant actions rather than hiding them ([NN/g, Contextual menus](https://www.nngroup.com/articles/contextual-menus/)).
- *State next to its actions.* Use a summary list for "key facts" with a row action per row. Add visually hidden text so a screen reader hears "Change name", not a bare "Change" ([GOV.UK Summary list](https://design-system.service.gov.uk/components/summary-list/)).
- *Confirm vs undo.* Use confirmation "before committing to actions with serious consequences". Avoid it for "routine actions", because people habituate to it and click Yes without reading. "Do try your best to offer undo" ([NN/g, Confirmation dialogs](https://www.nngroup.com/articles/confirmation-dialog/)).
- *Undo feedback.* A snackbar holds a single action such as Undo. On the web, avoid auto-dismissing it unless inline feedback is also shown ([Material 3 Snackbar](https://m3.material.io/components/snackbar/guidelines)). GOV.UK uses a green notification banner "to confirm that something they're expecting to happen has happened" ([Notification banner](https://design-system.service.gov.uk/components/notification-banner/)).
- *Pre-filled GitHub issues.* `title`, `body`, `labels` and `template` can be passed as URL query parameters. You "can also use URL query parameters to fill custom text fields" in issue forms. Too long a URL returns `414`, and missing permissions return a `404` ([Creating an issue from a URL query](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue#creating-an-issue-from-a-url-query)). A field's `id` "is the canonical identifier for the field in URL query parameter prefills" ([Form schema syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema)).

## 3. What they have in common

1. **Subject first, then verb.** ClassDojo, Classroom, Stripe, Salesforce and GitHub Collaborators all do this. None of them asks for the person again inside each action.
2. **Find the subject by typing.** GitHub and Stripe use search, and the APG combobox is the accessible way to build it.
3. **The subject's current state sits next to its actions.** The Salesforce header shows key fields, and GOV.UK puts a row action next to each fact. That answers "who has what" without a separate tool.
4. **Frequent verbs are buttons, rare ones go in "More".** Salesforce and Atlassian both do this. The menu needs a visible cue, and every action stays reachable.
5. **Multi-select turns the same verbs into bulk actions** (ClassDojo).
6. **Routine, reversible actions get undo, not a confirm dialog** (NN/g, Material, ClassDojo). Keep confirmation for consequential ones.
7. **Recent activity is shown per subject.** Classroom has a student's history, ClassDojo has Reports, Stripe shows a customer's payments.

## 4. Proposed design

### Layout

```
┌ Facilitator ────────────────────── Leaderboard ↗ ─┐
│ [ Find a person…            / ]                   │
├──────────────────────┬────────────────────────────┤
│ ☐ Asha Rao     95  #1│ Asha Rao   @asharao        │
│ ☐ Ben Okafor   70  #2│ 95 points · rank 1         │
│ ☐ benokafor-gh 10  #6│                            │
│ ☐ …                  │ [+1 help] [+1 stretch] [More ▾]
│                      │                            │
│ No one called "Priya"│ Exercises                  │
│ [Add Priya]          │  FizzBuzz        Correct   │
│                      │  REST API        Submitted  [Mark correct]
│                      │  Framework upg.  —          [Mark correct]
│                      │ Helps 2 · Stretch 1(+1 PR) · Bonus 0
│                      │                            │
│                      │ Recent changes for Asha    │
│                      │  Gave 1 help (Ben, 10:42)  │
├──────────────────────┴────────────────────────────┤
│ Changes: ● Gave 1 help to Asha — waiting for you  │
│          to press Submit on GitHub [Open again]   │
│          ✓ Renamed benokafor-gh → … landed [Undo] │
└───────────────────────────────────────────────────┘
```

With people ticked, the right pane becomes "**3 selected**: [+1 help] [+1 stretch] [Bonus…]", with the names listed and a **Clear** button.

### Person picker and roster

- One filter input above a **visible roster list**, not only a pop-up. With 10–40 people, the list itself answers "who has what". It is the Classroom left column. The input follows the APG combobox pattern (`role="combobox"`, `aria-controls` the list, `aria-activedescendant`). It matches name and every GitHub login, ignoring case and a leading `@`, the same way `onBoard()` does. Enter picks the highlighted person.
- Each row shows name, points and rank, computed with `readParticipants` and `rankParticipants` from `scoring.js`, so it agrees with the leaderboard. Sort by name by default, with an option to sort by points.
- Remember the selected person in the URL (`#p=asharao`), so Back and reload keep the selection, and the walkthrough can link to it.

### The person's state

Use a summary list (`<dl>`): one row per lesson from `lessons.json` with its status label (`RULES.labels`), then helps, stretch (own + PR credit, shown separately), bonus, logins, points and rank. Under it, the last 5 `history.json` entries whose `changes` touch this row.

### Actions

| Action | Where | Submits |
|---|---|---|
| +1 help, +1 stretch | Primary buttons | award `helped`/`stretch` `1` |
| Mark correct | Row action on each exercise that is not yet Correct; hidden text "Mark Asha's REST API correct" | mark `correct` |
| Bonus points…, Take one away… | More menu → small inline form (amount) | award with amount / `-1` |
| Set result… (submitted/none) | More menu, disabled with a reason when a PR earned more (the floor in `FACILITATOR.md`) | mark |
| Rename… | More menu, or a pencil icon on the name; inline field pre-filled with the current name | rename |
| Same person as… | More menu → second picker → side-by-side preview of the merged row (higher value per column) | merge, keep = this person |
| Add *typed name* | Roster footer when the filter matches nobody; GitHub username optional | add |
| Undo | In the Changes tray, only on the latest change in `history.json`, labelled with what it undoes ("Undo: Gave 1 help to Asha, by Ben") | undo |

The More menu follows the APG menu button pattern (`aria-haspopup="menu"`, arrow keys, Escape) and uses a visible ▾ cue. Every action runs through the existing `preview()` sentence ("Give 1 help to Asha Rao.") shown next to the GitHub button. The page drops `confirm()` for routine awards. It keeps one for undo, because undo reverses another facilitator's change, and the label must say exactly whose.

The page's actions still map one-to-one onto `FORMS` entries and workflows. ADR 0002 and `test_facilitator_page.py` keep holding. Only how the page *collects* inputs changes.

### Submission, progress and undo

1. The action builds the issue URL: `issues/new?template=<action>.yml&title=…&<field id>=<value>`, opened with `target="_blank" rel="noopener"`.
2. The tray adds an entry: "Waiting for you to press **Submit new issue** on GitHub", with **Open again** and a **See it in Actions** fallback link.
3. The page then reads `history.json` (unauthenticated contents API or Pages), every 10–15 s, but only while something is pending. When an entry matching the preview sentence and the facilitator appears, the tray shows "✓ Landed". The person pane updates and marks the change. While the change is in flight, the pane shows it as pending ("+1 help pending"), never as already counted.
4. After ~3 minutes with nothing seen, the entry says "Not seen yet: check the issue or the Actions tab".
5. Status text goes in one `aria-live="polite"` region. Entries stay until dismissed. Material advises against auto-dismissing on the web.

**Bulk.** Each workflow takes one `person`. Options: (a) one issue per person, which means N tabs and N Submit clicks; (b) the award issue form gets a `people` textarea, one name per line, and the workflow loops over it. (b) is one click and one history entry, so one undo reverses the whole batch. It needs a workflow and `roster.py` change, so treat it as a separate step. Until then, show "This opens 3 GitHub tabs".

### Keyboard and mobile

- `/` focuses the filter, Enter selects, Escape clears. `h` (+1 help) and `s` (+1 stretch) act on the selected person. Single-key shortcuts must be possible to turn off or limited to when focus is on the pane ([WCAG 2.1 SC 2.1.4](https://www.w3.org/WAI/WCAG21/Understanding/character-key-shortcuts.html)). `?` lists the shortcuts, as Stripe does.
- Below ~700 px the layout stacks: roster, then person, with a sticky "← All people". Buttons are at least 44 px tall, and the tray becomes a bottom sheet. Facilitators are mostly on laptops, so mobile only needs to work, not to be optimised.

### Accessibility

Use landmarks (`<nav aria-label="People">`, `<main>`) and the roster as a `listbox`. In bulk mode it becomes a list of checkboxes. Every action's accessible name includes the person ("Give a help to Asha Rao"). After an action, focus stays where it was, and the live region announces the result. Statuses use words, not only colour (GOV.UK banner guidance). Keep the current colour tokens and `:focus-visible`.

## 5. Risks, trade-offs and tests

- **Prefill coverage is unverified.** GitHub documents prefills for "custom text fields". Whether `dropdown` fields (kind, status) prefill from a URL is not stated. Use `input` fields that the workflow validates, or test dropdowns on the sandbox first.
- **Anyone who can open an issue can submit the form.** The workflow must check the issue author's permission before applying, which a `workflow_dispatch` token used to guarantee. That is a security requirement, not UI.
- **No authentication means rate limits.** Unauthenticated API reads are limited per IP, and several facilitators on one venue network share that limit. Pages-served `history.json` avoids the limit but lags by a deploy. Poll only while something is pending.
- **Undo is global.** Between pressing Undo and the run landing, another facilitator's change can become the latest. Undo should carry the expected top entry and refuse if it changed. That is another workflow input.
- **Hiding verbs in More** slows the rare journeys (rename is frequent early in a session). Consider surfacing **Rename** as a primary button for rows whose name equals a login.
- **The walkthrough** (`walkthrough/facilitator-steps.js`) targets `form-*` tours. Its steps need rewriting around the picker, and `test_every_tour_step_target_is_on_the_page` will catch stale targets.

**Browser tests.** Run them against the practice server (`facilitator_walkthrough.py`), skipped when no browser driver is installed, like `needs_node`. One test per journey:

1. Type part of a login → pick → **+1 help** → the tray lands → the pane shows helps +1 and points +5 (matches `pointsOf`).
2. Rename from a login-named row; the roster shows the new name and the selection stays.
3. **Mark correct** appears only on non-Correct exercises, and lands.
4. Tick 3 people → +1 stretch → three people updated (or three issue URLs, under option a).
5. Filter for an unknown name → **Add** → the person appears and is selected.
6. **Same person as…** → preview shows the higher value per column → merge lands, and the duplicate is gone from the roster.
7. **Undo** shows only on the latest change, names it, and reverses it. A stale undo is refused.
8. Keyboard only: `/`, arrows, Enter, `h`, Escape, the More menu. Run an axe check on each state.
9. At 375 px wide: no horizontal scroll, and the roster ↔ person navigation works.
10. Unit test: the issue URL builder produces the right `template` and field ids for every `FORMS` entry, and stays under the length limit.
