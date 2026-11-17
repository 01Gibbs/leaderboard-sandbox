# Two tabs on the facilitator page: Workshop and People

*Research note, 17 November 2026. Audience: project lead.*

> **Status (17 Nov 2026).** Built: the Workshop and People tabs, the lessons list with each lesson's state, Remove and Try again, and the Add a lesson form with its checks before sending. The open questions were settled the simple way: one Recent changes list (on People); Back leaves the page; one line on Workshop points to People; a failed lesson offers **Try again** (remove and add again, in one Send); no sticky Send bar for now; Add a lesson is shown to every facilitator (they are all collaborators).

> **Decision already taken (project lead):** one page, two tabs. **Workshop** is the default: grading status and **Grade now**, the lessons with each one's state, and the **Add a lesson** form. **People** is today's person-first view, for adjustments. The **Changes** box and **Send** are shared by both tabs: still one issue per Send, in one reused GitHub tab. This note works out the details.

## Recommendation

Put a tab list under the header and two panels beside **one shared Changes column**. Workshop opens first. People is one click, one arrow key, the `/` key, or a link ending `#people`. Today's three-column grid becomes "the active panel | Changes" ([1] lines 44, 112–149). The Changes box looks and behaves exactly as it does now, so the 18 journeys that use People keep passing once they open `#people` (see [Browser journeys](#browser-journeys-to-add-or-change)).

Tabs suit this split. GOV.UK says to use them when content "can be usefully separated into clearly labelled sections", when "users will not need to view all the sections at once", and when "the first section is more relevant than the others for most users". It adds that tabs "can work well for people who use a service regularly" [26]. Facilitators are regular users. They never need to compare grading with a person's row. Its warnings do not apply here either: tabs are not used "as a form of page navigation", and there is no step-by-step order across them [26]. The real risk is the one GOV.UK names: "Tabs hide content from users and not everyone will notice them" [26]. That is why the tour gains a step on the tabs and Workshop links across to People (below).

### Workshop, laptop width (about 1280 px)

```
┌ Facilitator                                  Leaderboard ↗   Shortcuts ─────────────────┐
│ [ Workshop ]   People                                         ← role=tablist             │
├────────────────────────────────────────────────────────────┬────────────────────────────┤
│ Grading                                                    │ Changes                    │
│ Last graded 12 minutes ago: see the run. New pull requests │ Remove lesson Greeting.    │
│ are also graded once a day by themselves.                  │   Not sent yet     Remove  │
│ [Grade now]                                                │                            │
│                                                            │ [ Send 1 change ]          │
│ Lessons                                                    │ Opens GitHub with them     │
│  FizzBuzz            Live                                  │ filled in: press Submit    │
│  REST API            Live                                  │ new issue there. Only the  │
│  …                                                         │ leaderboard's collaborators│
│  Greeting            Checking: tried at the next grading   │ can make changes.          │
│                      run                        [Remove]   │                            │
│  Roman numerals      Failed its trial: the pinned tests do │                            │
│                      not compile against the starter       │                            │
│                      ▸ Full reason · tried again after     │                            │
│                        14:05 tomorrow           [Remove]   │                            │
│                                                            │                            │
│ ▸ Add a lesson                                             │                            │
│                                                            │                            │
│ Points, names and results: see People.                     │                            │
└────────────────────────────────────────────────────────────┴────────────────────────────┘
```

With **Add a lesson** open (the fields and pre-checks from [7], "The form's fields"):

```
│ ▾ Add a lesson                                                                   │
│   Exercise repository  [ owner/name, or its GitHub link        ]                 │
│                        Public · Gradle project · 7 test files under src/test     │
│   Name shown           [ Roman numerals                        ]                 │
│   Column key           [ roman_numerals                        ]  (made from name)│
│   How it is graded     (•) Its tests  ( ) It builds  ( ) A facilitator marks it  │
│   Where the tests are  (•) In the exercise repository  ( ) Somewhere else        │
│   [ Add to changes ]                                                             │
```

### People, laptop width

```
┌ Facilitator                                  Leaderboard ↗   Shortcuts ─────────────────┐
│   Workshop   [ People ]                                                                  │
├──────────────────────┬─────────────────────────────────────┬────────────────────────────┤
│ [Find a person…   /] │ Asha Rao   @asha-rao  95 points · #1│ Changes                    │
│ ☐ Select several 12/12│ [+1 help] [+1 stretch] [More ▾]     │ Give 1 help to Asha Rao.   │
│ Asha Rao     95 · #1 │ FizzBuzz        Correct             │   Not sent yet     Remove  │
│ Ben Okafor   70 · #2 │ REST API        Submitted  Mark corr.│ [ Send 1 change ]          │
│ …                    │ Helps 2 · Stretch 1 · Bonus 0       │                            │
│ No one called "Priya"│ Recent changes for Asha Rao         │                            │
│ Add Priya            │  Gave 1 help … (Ben, 10:42)  Undo   │                            │
│                      │                                     │                            │
│                      │ Recent changes (everyone)           │                            │
│                      │  Renamed benok to Ben Okafor  Undo  │                            │
└──────────────────────┴─────────────────────────────────────┴────────────────────────────┘
```

This is today's page with **Grading** taken out of the right-hand column. **Recent changes** moves out of that column too, into the People panel under the person.

### On a phone (700 px or narrower)

Everything stacks in one column, as today ([1] lines 90–94). Order: header, banners, the tab list as two equal halves (each at least 44 px tall, as today's buttons are [1] line 93), the active panel, then Changes.

```
Workshop tab                       People tab
┌──────────────────────────┐       ┌──────────────────────────┐
│ Facilitator  Leaderboard │       │ Facilitator  Leaderboard │
│ [ Workshop ][  People  ] │       │ [ Workshop ][  People  ] │
│ Grading … [Grade now]    │       │ [Find a person…       /] │
│ Lessons                  │       │ Asha Rao … (max 40vh)    │
│  FizzBuzz        Live    │       │ Asha Rao  95 · rank 1    │
│  Greeting   Checking …   │       │ [+1 help][+1 stretch]    │
│ ▸ Add a lesson           │       │ [More ▾]  exercises …    │
│ Changes                  │       │ ▸ Recent changes         │
│ [ Send 1 change ]        │       │ Changes  [ Send … ]      │
└──────────────────────────┘       └──────────────────────────┘
```

On a phone, People's two **Recent changes** lists fold into one closed `<details>` [22]. That keeps Changes and Send right below the person after a tap on **+1 help**. Today, on a phone, Send sits below ten history rows.

## Journeys

Clicks are counted from the page as it opens, on Workshop. Typing is not a click. Every change then needs the same two steps, written **+2** below: **Send** on the page, and **Submit new issue** on GitHub [1] lines 571–591. The feedback for a change is also always the same: a row in Changes, "Not sent yet", then "Waiting for Submit on GitHub", then **Done** (it fades) or **Not done** with the reason [1] lines 540–563, 612–649. The polite live region also says "Added to Changes: …" [1] line 537.

| Journey | Tab | Clicks to queue it | Feedback beyond the Changes row |
|---|---|---|---|
| Give a help or a stretch | People | 3: **People**, pick, **+1 help**. Keyboard: `/` (switches to People), type, Enter, `h`. That is 0 clicks. **+2** | The person's Helps and points update when the row is done ([1] line 640 reloads the board) |
| Give bonus points / take some away | People | 5: People, pick, **More**, **Bonus points…** or **Take some away…**, **Add to changes** (plus the amount, and "What" for take away). **+2** | Page checks before GitHub, e.g. "has 0 helps; cannot take away 1" [1] line 528 |
| Set a result | People | **Mark correct**: 3 (People, pick, Mark correct). Another result: 6 (People, pick, More, **Set a result…**, choose, Add). **+2** | Hint "A result cannot go below what a pull request earned" [1] line 471; GitHub's refusal shows on the row |
| Rename | People | 5: People, pick, More, **Rename…**, Add. **+2** | "already on the board" stops it on the page [1] line 480 |
| Merge | People | 6: People, pick the row to keep, More, **Same person as…**, choose the duplicate, Add. **+2** | Preview table of the row as it will be [1] lines 506–520 |
| Add a person | People | 3: People, type the name, **Add *name***, (GitHub username), Add to changes. That is 4 with the username field. **+2** | They appear in the list once done |
| Undo one change | People | 2: People, **Undo** next to it (everyone's list, or the person's). **+2** | The button reads "Undo waiting" and is disabled until done [1] lines 674–677 |
| Grade now | Workshop | 1: **Grade now**. Then **Run workflow** twice on GitHub. | Hint under the button; "Grading now, started …" then "Last graded …" with a link to the run; "Grading finished: scores updated." in the live region [1] lines 245–295 |
| Add a lesson | Workshop | 2–4: open **Add a lesson**, (choose how it is graded, and where the tests are), **Add to changes**. **+2** | Pre-checks under the repository field before sending [7]. Once done, the lesson shows as **Checking** in Lessons, then **Live** or **Failed its trial** after the grading run that the push starts [13] |
| See why a lesson failed its trial | Workshop | 0 to see the first line, 1 for **Full reason** | The reason, and when it is tried again (below) |
| Remove a lesson | Workshop | 1: **Remove** next to the lesson. **+2** | It leaves the Lessons list when done; the row's message says "Its results are kept: adding it again brings them back" [8] lines 60–75 |

Nothing that used to be on the page has more clicks than before, except the one **People** click. A link to `facilitator.html#people`, `/`, and the arrow keys all avoid it.

## What to remove, simplify or move

Line numbers are `facilitator.html` on `main` [1].

| Today | Lines | Change |
|---|---|---|
| Header comment "pick a person, then act" | 9–10, 163–173 | Describe the two tabs. |
| `#how` banner: four lines about Send, always shown on the real page | 106–108, 728 | **Remove.** Move its one sentence that `#sendHint` does not already say ("Only the leaderboard's collaborators can make changes") into `#sendHint` (line 562). It then shows only when there is something to send, in the box it explains. |
| `main` as three columns: roster, person, side | 44, 89–94, 112–149 | `main` becomes "panel, 330 px Changes". The People panel holds its own two columns (roster 280 px, person). At ≤1000 px Changes goes below. At ≤700 px everything is one column. |
| `#grading` panel in `#side` | 137–142 | **Move** into the Workshop panel, first. Unchanged inside. |
| "Recent changes" panel in `#side` | 143–147 | **Move** into the People panel, under the person. On a phone, fold it into a closed `<details>` [22]. |
| `#side` | 129–148 | Holds only `#changes`. Rename it `#shared`, or keep the id. |
| `<ul id="people">` (the roster listbox) | 121, 116 (`aria-controls`), 326, 696, 701 | **Rename** to `id="roster-list"`. The hash `#people` must not match any element's id, or the browser scrolls to it on load (below). |
| Lessons loaded once from the Pages copy, checking ones dropped | 301–302 | Keep that filtered list for the person pane, the merge preview and "Set a result". `test_neither_page_shows_a_lesson_still_being_checked` pins the filter [16]. Workshop needs a second, **unfiltered** list read through the contents API (below). When it changes, refresh the filtered one too, so a lesson that goes live grows its row in the person pane without a reload. |
| `/` focuses `#find` | 687 | First activate the People tab, then focus `#find`. |
| `h` and `s` act on the person picked | 690–692 | Also require the People panel to be showing. Otherwise `h` on Workshop silently gives a help to someone out of sight. The shortcuts can already be turned off, which meets WCAG 2.1.4 [31]. Keep that. |
| Shortcuts dialog | 151–158 | Add "`←` `→` switch tabs (on a tab)". |
| Grading read on start | 718–719 | Unchanged: Workshop is the default, so it is wanted at once. |
| `data-tour="how"`, `data-tour="add"` | 106, 122 | `how` goes with the banner. No step targets either [3]. |

Nothing else is dropped. **Select several**, the More menu, the merge preview and the keyboard list are what the 18 People journeys use [15].

## The tabs' accessibility

Follow the WAI-ARIA Tabs pattern [19] and its automatic-activation example [20].

**Markup.**

```html
<div role="tablist" aria-label="Facilitator" data-tour="tabs">
  <button type="button" role="tab" id="tab-workshop" aria-controls="workshop-panel" aria-selected="true" tabindex="0">Workshop</button>
  <button type="button" role="tab" id="tab-people" aria-controls="people-panel" aria-selected="false" tabindex="-1">People</button>
</div>
<section role="tabpanel" id="workshop-panel" aria-labelledby="tab-workshop" tabindex="0">…</section>
<section role="tabpanel" id="people-panel" aria-labelledby="tab-people" tabindex="0" hidden>…</section>
<aside id="shared" aria-label="Changes">… #changes …</aside>
```

- `role="tablist"` on the container, `role="tab"` on each tab inside it, `role="tabpanel"` on each panel [19].
- The active tab has `aria-selected="true"` and the other `false`. Each tab has `aria-controls` pointing at its panel. Each panel has `aria-labelledby` pointing at its tab [19].
- Use `<button>` elements for the tabs. MDN recommends "a `<button>` element with the role `tab` for their built-in functional and accessible features" [21], and the APG example does the same [20].
- Roving tabindex: the active tab has `tabindex="0"` and the other `-1`. MDN says these "must always be coordinated" with `aria-selected` [21].
- The inactive panel has the `hidden` attribute [21]. The page already forces `[hidden] { display: none !important }` ([1] line 24).
- Each panel has `tabindex="0"`. Neither panel starts with something focusable (Workshop starts with the "Grading" heading, People with the search box only after the roster heading). The APG says a panel without focusable content first "should set tabindex="0"" [19], and MDN says that in that case "all tabpanel elements in a tab set should be focusable" [21].
- The Changes box sits outside both panels, in its own labelled landmark, so it is reachable from either one.

**Keys** [19][20]:

| Key | On a tab |
|---|---|
| Tab | Into the tab list: focus goes to the *active* tab. Out of it: into the active panel. |
| → / ← | Next / previous tab, wrapping from the last to the first and back. The tab is activated as it is focused. |
| Home / End | First / last tab, activated. Optional in the pattern; cheap with two tabs. |
| Space / Enter | Activate (already done on focus; harmless). |

**Automatic activation.** "It is recommended that tabs activate automatically when they receive focus", unless showing a panel has "noticeable latency" [19]. Here both panels are already in the page and only `hidden` changes, so switching is instant. GitHub reads happen in the background and fill in when they arrive. Switching never re-renders a panel, so a half-filled Add a lesson form or a merge preview survives a trip to the other tab.

**Focus.** Activating a tab leaves focus on the tab. The keyboard user then presses Tab to go into the panel, as the pattern expects [19]. Exceptions: `/` moves focus to `#find` (that is its job), and Enter in `#find` focuses the person's heading, as today ([1] line 711).

**The URL** (so a tab can be linked).

- `#workshop` and `#people` name the tabs. On load, read `location.hash`. `#people` opens People. Anything else, or nothing, opens Workshop.
- GOV.UK updates the URL "with a fragment" when you change tab, so the browser's Back button "should navigate back to the previous tab" [26]. GOV.UK uses the panel's `id` as the fragment [26]. Do **not** copy that part here. A fragment that matches an element's id makes the browser "scroll to that element" [24]. On load that would scroll the tab list off the top of a phone screen. Today `#people` is also already the roster's `<ul>` id [1] line 121, and ids "must be unique" [23]. So the panels are `workshop-panel` and `people-panel`, the roster list becomes `roster-list`, and no element has the id `workshop` or `people`.
- On a tab change, set the hash with `history.replaceState(null, '', '#people')`. That keeps `?practice` and `?repo=` (it changes only the fragment) and adds no history entry, and `hashchange` does not fire for it [25]. Back then leaves the page rather than walking through tab switches. GOV.UK prefers the opposite; this is open question 2.
- Listen for `hashchange` [25]. It fires when someone edits the address, follows a `#people` link in the same page, or (below) when the tour sets the frame's hash.

**Words, not colour.** Lesson states are words ("Live", "Checking", "Failed its trial"), as row states already are ([1] line 546), with the same `ok` and `bad` colours as a second cue.

## A lesson's state, read without a token

Everything the Workshop list needs is already in two public files on `main`. The page reads files through `github-reader.js`, which keeps every read within one budget of 50 an hour, asks only for what changed (ETags), and waits out GitHub's limit [2]. `readState(path, empty)` reads a file's raw contents through `GET /repos/{repo}/contents/{path}?ref=main` with `application/vnd.github.raw+json` [1] lines 222–228. That media type "Returns the raw file contents". It works for files up to 100 MB; above 1 MB "only the raw or object custom media types are supported" [27]. `grader/results.json` is 28 KB today.

**1. `lessons.json` through the API, not the Pages copy.** Pages republishes `lessons.json` only on a deploy [14]. A lesson added, put live or removed reaches the API copy first. Read it with `readState('lessons.json', [])`, unfiltered. Each item's `status` is `"checking"` until its trial passes and is absent once it is live ([12] lines 26–27, 47). `check` says whether the page may offer **Remove**. Only `none`, `build` and `tests` lessons can be removed from the page; a custom check is "removed through a pull request" [8] lines 60–71. All five current lessons have custom checks, so none shows Remove today.

**2. `grader/results.json`, its `trials` section.** The grading job tries each checking lesson and records `trials[key] = {version, passed, reasons, at}`. `passed` is `true`, `false` or `null` (the grader itself failed) [10] lines 91–110. A passing trial puts the lesson live in the same save that records it [11] lines 373–389. Adding or removing a lesson forgets its trial [8] lines 43, 54–57, 74.

| `lessons.json` | `trials[key]` | Shown |
|---|---|---|
| no `status` | any | **Live** |
| `checking` | none | **Checking**: "tried at the next grading run". A push to `lessons.json` or `grader/fixtures/**` starts one [13]. |
| `checking` | `passed: null` | **Checking**: "the grader could not finish; it tries again at the next grading run" [9] lines 25, 58–59; [10] line 95 |
| `checking` | `passed: false` | **Failed its trial**: the first line of `reasons[0]`. The full text goes in a `<details>` [22] as preformatted text, with "Tried again after *at* + 24 h, or when the lesson changes". A failed trial is retried "a day after it failed" [9] lines 11–13, 21 |
| `checking` | `passed: true` | **Checking** ("being tried again"). The page cannot work out the trial version, which hashes the lesson and `trial.py` [12] lines 74–79. A passed trial that left the lesson checking must be for an older version. |

Failure reasons hold Gradle output from someone else's repository [9] lines 42, 53. Set them with `textContent`, as the page's `el()` already does ([1] lines 192–197), never as HTML.

**When to read** (each read costs one of the 60 an hour shared by the venue; GitHub counts unauthenticated reads even when the answer is "not modified", because its exemption needs an `Authorization` header [29][30]):

- On load: `lessons.json` and `grader/results.json`, two reads. With the grading run and `history.json`, that makes 4, against 2 today.
- When an `add-lesson` or `remove-lesson` row is **Done**: re-read `lessons.json`, then follow the `grade.yml` run its push started. The page's `latestGrading(event)` already reads `.../actions/workflows/grade.yml/runs?per_page=1&event=…` [1] lines 239–243. The endpoint "Returns workflow run triggered by the event you specify" [28]. Use `event=push` here, with the same `github.poll` as Grade now. When that run completes, re-read both files. Results.json is saved by that run, so the new trial is there.
- When a Grade now run completes ([1] line 287 already reloads the board): re-read both.
- No standing poll. Trials only change in a grading run, and the page already watches the two kinds of run that a facilitator starts.

**Practice copy.** `facilitator_walkthrough.py`'s stand-in GitHub answers only `contents/grader/history.json` and `batches.json` [17] lines 146–157. It needs `contents/lessons.json` and `contents/grader/results.json` too (with ETags, as those have). Its `practice_results` should seed one checking lesson and one failed trial, so the tour and the tests can show all three states.

## Tour steps to add or change

`tour.js` highlights the first *visible* element with the step's `data-tour` name, and says "hidden at this window size" when there is none [4] lines 49–100. A target inside the hidden tab therefore fails. Add an optional `tab` field to a step. Before it looks for the target, `tour.js` sets `frame.contentWindow.location.hash` to it. That fires `hashchange` in the frame [25], and the page switches tab. Steps without `tab` (the leaderboard tour, `steps.js`) are unaffected.

| Step [3] | Change |
|---|---|
| 1 "The facilitator page" (stage) | Retitle "Two tabs". Cards: **Workshop** (grade, lessons), **People** (find someone, act), **Changes** (wait in one box, shared by both tabs), **Undo**. |
| 2 "This is a practice copy" | Unchanged. |
| *new* "Two tabs", target `tabs` | "Workshop is where you start: grading and lessons. People is for points, results, names and mistakes. ← and → switch between them; a link ending #people opens People." |
| *new* "Grade new pull requests now", target `grading`, `tab: 'workshop'` | Moved here from chapter "Changes" (old step 8), text unchanged. |
| *new* "The lessons", target `lessons`, `tab: 'workshop'` | "Each lesson and its state: Live, Checking (tried at the next grading), or Failed its trial with the reason. Remove takes one away; its results are kept." |
| *new* "Try it: add a lesson", target `add-lesson`, `tab: 'workshop'` | Once slice 2 of [7] is built: the form, its pre-checks, "it waits in Changes like anything else". |
| 3–5 "find someone", "where they stand", "give a help" | Add `tab: 'people'`. Step 3's text: "Press `/` (it opens People) …". |
| 6–7 Changes | Add `tab: 'people'` (so the box still shows the help from step 5). Add "The same box on both tabs". |
| 8 Grade now | Moves up (above). |
| 9 "Undo just one change", `history` | `tab: 'people'`. |
| 10–12 Several, Someone new, Renaming | `tab: 'people'`. |
| 13 "That's it" | "Workshop to grade and add lessons; People for everything about a person; one Submit for everything." |

`test_every_tour_step_target_is_on_the_page` [16] keeps catching stale targets. Add a sibling test: every target of a step with `tab: 'x'` sits inside `#x-panel`. The text test can check this by locating the `data-tour` inside the panel's markup or its render function.

## Browser journeys to add or change

The 20 journeys in [15] keep their meaning. These are the edits.

**Change (mechanical):**

1. `setUp` opens `/facilitator.html?practice#people`, not `?practice` (line 60). It waits for `#roster-list li`. The 18 People journeys are then untouched apart from the selector.
2. `#people li` becomes `#roster-list li` (6 places: lines 62, 191, 239, 259, 274, 296).
3. `test_works_on_a_phone_sized_screen` (237–242) opens `#people` and checks the order tab list < roster < person < Changes. It also checks no sideways scroll on **Workshop** (open without a hash).
4. `test_grade_now_in_practice_says_what_it_would_do` (321–323) clicks the **Workshop** tab first. That proves Grade now lives there.
5. Tests that open `?repo=someone/board` and pick a person (`test_a_blocked_github_tab_keeps_the_changes` 311, `test_on_the_real_page_send_…` 347) add `#people`. `test_a_change_github_never_makes…` (272) and `…limits_reads…` (286) open `?practice&timeout=2#people`.
6. `test_on_the_real_page_send_…` line 348 expects `#how` visible. With the banner gone, expect `#sendHint` to say "Only the leaderboard's collaborators" once a change waits.
7. `test_on_the_real_page_grade_now_opens_grade_submissions` (325–340) needs no change: no hash means Workshop.

**Add:**

8. *Workshop is the default and tabs are a tablist.* Open without a hash: the Workshop tab has `aria-selected=true`, `#people-panel` is hidden, `get_by_role('tab', name='People')` exists. Then press → on the focused tab: People is selected, its panel shows, the URL ends `#people`, and the query string is kept. Press End and Home, then → on the last tab wraps to the first.
9. *A link opens a tab.* `?practice#people` shows People. Changing the hash to `#workshop` (as the tour does) switches back.
10. *`/` from Workshop opens People and focuses the search.* `h` pressed on Workshop queues nothing.
11. *The Changes box is shared.* Queue a help on People, switch to Workshop: the row and **Send 1 change** are still visible. Send from there, and it is done.
12. *Lessons show their state.* On the practice copy seeded per [the practice copy](#a-lessons-state-read-without-a-token): a live lesson says Live, the checking one says Checking, and the failed one says "Failed its trial" with the first line of the reason. **Full reason** opens the rest. The checking and failed lessons are **not** in the person pane (they are still hidden there).
13. *Remove a lesson.* **Remove** shows only on lessons checked with `none`, `build` or `tests`. Press it on the failed lesson, Send: Done, and the lesson leaves the list and `lessons.json`.
14. *Add a lesson* (slice 2 of [7]): fill the form on the practice copy, Send: Done, and it shows as Checking. Pre-check failures (a taken key, no `gradlew` offering only "a facilitator marks it") are stopped on the page. [7] already lists these as slice 2's evidence.
15. *Reads stay frugal.* Count requests to `practice-api` on load: at most 4 (lessons, results, history, grading run in real mode; practice has no runs).

## Open questions

1. **Recent changes:** one place or two? Today the person pane shows that person's last five, and the side shows everyone's last ten ([1] lines 391, 667). This note keeps both on People. Could the everyone list be the only one, filtered to the person when one is picked?
2. **Back button.** `replaceState` (recommended: Back leaves the page) or a history entry per tab switch (GOV.UK: Back returns to the previous tab [26])?
3. **"Points, names and results: see People"** on Workshop is the only cue for a facilitator who never notices tabs [26]. Is a line enough, or should Workshop also show a short "Last 3 changes" with a link?
4. **Remove a checking lesson that failed, or fix it in place?** A failed lesson can only be re-tried by waiting a day, or by removing and adding it again [9][8]. Should the Failed row offer **Try again now** (a `remove-lesson` row plus an `add-lesson` row with the same fields, in one Send)? It needs the original fields, which `lessons.json` has.
5. **Phone Send.** Is folding Recent changes enough, or should a "N changes waiting · Send" bar stick to the bottom of the screen while something waits?
6. **Facilitators who should not add lessons.** Everyone with write access can, by design [7]. Should Workshop hide **Add a lesson** behind `?lessons`, so that day-to-day facilitators see only Grade now and the list?

## Sources

Repository (`main` at ccb14b4 unless marked; `lesson-trial` means the worktree `.claude/worktrees/lesson-trial`, commit 193d00f plus its uncommitted changes):

1. `facilitator.html`: 9–10 (comment), 24 (`[hidden]`), 44, 89–94 (grid and breakpoints), 104–110 (banners), 112–149 (layout), 151–158 (shortcuts dialog), 192–197 (`el`), 222–228 (`readState`), 239–295 (grading), 298–312 (lessons and board), 323–349 (roster), 356–395 (person pane), 524–563 (Changes box), 571–608 (Send, one GitHub tab), 612–653 (follow), 666–681 (history and Undo), 685–722 (keys), 725–732 (start)
2. `github-reader.js`: 1–9 (one budget, ETags, limits), 30–58 (`read`), 65–82 (`poll`)
3. `walkthrough/facilitator-steps.js`: 1–116
4. `walkthrough/tour.js`: 49–100 (`findTarget`, visible targets only)
5. `FACILITATOR.md`: 5–29
6. `docs/research/facilitator-ui.md`: journeys and the person-first design
7. `docs/research/lessons-from-the-page.md`: decisions, the form's fields, pre-checks, build plan (slice 2)
8. `grader/lesson_changes.py` (lesson-trial): 22–51 (`add`, saved as checking), 54–57 (`forget_trial`), 60–75 (`remove`)
9. `grader/trial.py` (lesson-trial): 1–13 (what a trial does, retries), 21 (`RETRY_FAILED_AFTER`), 24–59 (`run`, reasons)
10. `grader/submissions.py` (lesson-trial): 91–110 (`needs_trial`, `record_trial`, `trials` shape)
11. `grader/roster.py` (lesson-trial): 373–389 (`apply_results` puts a passed lesson live)
12. `grader/lessons.py` (lesson-trial): 26–27 (`status`, `CHECKING`), 47, 74–79 (`trial_version`)
13. `.github/workflows/grade.yml` (lesson-trial): `push` on `lessons.json` and `grader/fixtures/**`
14. `.github/workflows/pages.yml`: 35 (what Pages copies: `lessons.json`, not `grader/results.json`)
15. `grader/tests/test_facilitator_browser.py`: the 20 journeys, lines 99–367
16. `grader/tests/test_facilitator_page.py`: 52–61 (tour targets; checking lessons filtered)
17. `facilitator_walkthrough.py`: 118–170 (the stand-in GitHub API)
18. `grader/leaderboard.py`: 34 (`BATCHABLE` includes `add-lesson`, `remove-lesson`)

Standards and documentation (read 17 November 2026):

19. WAI-ARIA Authoring Practices Guide, Tabs pattern (roles, `aria-selected`, `aria-controls`, `aria-labelledby`, panel `tabindex="0"`, keyboard, automatic vs manual activation): https://www.w3.org/WAI/ARIA/apg/patterns/tabs/
20. WAI-ARIA APG, Tabs with automatic activation example (`button` tabs, `tabindex="-1"` on inactive tabs, arrow keys wrap and activate): https://www.w3.org/WAI/ARIA/apg/patterns/tabs/examples/tabs-automatic/
21. MDN, ARIA `tab` role (use `<button>`; roving tabindex coordinated with `aria-selected`; `hidden` on inactive panels; panel focusability): https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/tab_role
22. MDN, `<details>` ("a disclosure widget"; `<summary>`; `open`; `toggle`): https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/details
23. MDN, `id` global attribute ("must be unique within the entire document"; used for fragment links): https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/id
24. MDN, URI fragment ("the browser will scroll to that element"): https://developer.mozilla.org/en-US/docs/Web/URI/Reference/Fragment
25. MDN, `hashchange` event (does not fire for `pushState()` or `replaceState()`): https://developer.mozilla.org/en-US/docs/Web/API/Window/hashchange_event
26. GOV.UK Design System, Tabs (when to use, when not, "Tabs hide content", URL fragment and Back, small screens "more research is needed", not yet tried in research): https://design-system.service.gov.uk/components/tabs/
27. GitHub REST, Get repository content (`application/vnd.github.raw+json`; size limits 1 MB / 100 MB): https://docs.github.com/en/rest/repos/contents#get-repository-content
28. GitHub REST, List workflow runs for a workflow (`event`, `per_page`, `status`, `conclusion`): https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-workflow
29. GitHub REST, Rate limits (unauthenticated: "only fetching public data", "60 requests per hour", by IP): https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
30. GitHub REST, Best practices (a `304` is free only "while correctly authorized with an `Authorization` header"): https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
31. W3C, Understanding WCAG 2.1 SC 2.1.4 Character Key Shortcuts (turn off, remap, or active only on focus): https://www.w3.org/WAI/WCAG21/Understanding/character-key-shortcuts.html
