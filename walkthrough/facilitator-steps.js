// The facilitator walkthrough's content: one entry per step, shown by tour.js over the facilitator page
// (../facilitator.html?practice), which facilitator_walkthrough.py serves on a practice copy with made-up people.
// Steps work like steps.js: `target` is a data-tour name in facilitator.html, `stage` is HTML shown instead.
// "Try it" steps leave the page usable: the reader fills in the highlighted form for real, on the practice copy.

export function steps(ctx) {
  const someone = ctx.people[0] || 'Asha Rao', other = ctx.people[1] || 'Ben Okafor';
  const lesson = ctx.lessons[0] || { key: 'fizzbuzz', label: 'FizzBuzz' };
  const page = ctx.pages_url ? `<a href="${ctx.pages_url}facilitator.html" target="_blank" rel="noopener">${ctx.pages_url}facilitator.html</a>` : 'the leaderboard’s address, followed by <code>facilitator.html</code>';
  return [
    // ---------- 1. The page ----------
    {
      chapter: 'The page',
      title: 'The facilitator page',
      stage: `
        <h2>Changing the leaderboard</h2>
        <p class="lead">Everything a facilitator changes (points, results, names, duplicates, mistakes) is a form on one page.
          This tour runs that page on a <b>practice copy</b> with made-up people, so try anything.</p>
        <div class="cards">
          <div class="card"><b>Award points</b><span>helps, stretch tasks, bonus points</span></div>
          <div class="card"><b>Mark an exercise</b><span>a result you checked by hand</span></div>
          <div class="card"><b>Add, rename, merge</b><span>keep one tidy row per person</span></div>
          <div class="card"><b>Undo</b><span>reverse the latest change</span></div>
        </div>
        <p class="hint">Use <kbd>→</kbd> and <kbd>←</kbd> or the buttons. On a step that says <b>Try it</b>, use the page itself.</p>`,
      text: `<p>The real page is at ${page}.</p><p>Each form starts the same GitHub workflow as the matching <b>Facilitator:</b> form in the Actions tab, so either way does the same thing.</p>`,
    },
    {
      chapter: 'The page',
      title: 'This is a practice copy',
      target: 'practice',
      text: '<p>The banner says you are practising. Nothing here reaches GitHub or the real leaderboard; when you close the walkthrough, the practice copy is thrown away.</p>',
    },
    {
      chapter: 'The page',
      title: 'On the real page, Save opens GitHub',
      stage: `
        <h2>One more click, on GitHub</h2>
        <p class="lead">On the real page, Save opens GitHub with your change already filled in, as a new issue.</p>
        <ol class="flow">
          <li><b>Save</b><span>on this page: GitHub opens in a new tab</span></li>
          <li><b>Submit new issue</b><span>on GitHub, signed in as yourself</span></li>
          <li><b>About a minute</b><span>the change is made, and the issue is answered with what happened and closed</span></li>
        </ol>`,
      text: '<p>Only the leaderboard’s collaborators can make changes: GitHub checks who submitted the issue, and an issue from anyone else changes nothing. The repository owner adds collaborators under Settings → Collaborators.</p><p>No token, nothing to set up. Each form also links to the same form in the repository’s Actions tab.</p>',
    },

    // ---------- 2. Points and results ----------
    {
      chapter: 'Points and results',
      title: 'Try it: award a help',
      target: 'form-award',
      text: `<p>Someone helped a colleague. In <b>Award points</b>, start typing <b>${someone}</b> in Person and pick them, leave <b>helped</b> and <b>1</b>, and press <b>Save</b>.</p>
        <p>The line under the fields says what will happen before you press it.</p>`,
    },
    {
      chapter: 'Points and results',
      title: 'Watching it happen',
      target: 'activity',
      text: '<p>Each change you start shows here: <b>Saving…</b>, then <b>Done</b> or <b>Not changed</b> with the reason. On the real page it takes about half a minute, and the leaderboard shows it a minute or two later.</p><p>A mistake, like a misspelt name, changes nothing and says why.</p>',
    },
    {
      chapter: 'Points and results',
      title: 'Try it: take one away',
      target: 'form-award',
      text: `<p>Points given by mistake? Award <b>-1</b> of the same kind. Try taking the help back from ${someone}.</p>`,
    },
    {
      chapter: 'Points and results',
      title: 'Try it: mark an exercise',
      target: 'form-mark',
      text: `<p>For an exercise you checked yourself, set the result by hand. Mark <b>${other}</b>'s <b>${lesson.label}</b> as <b>correct</b>.</p>
        <p>You can’t mark a result <i>lower</i> than a pull request earned: the grader would put it straight back. If a pull request should not count, it has to be closed without merging.</p>`,
    },

    // ---------- 3. People ----------
    {
      chapter: 'People',
      title: 'Add someone',
      target: 'form-add',
      text: '<p>For someone who hasn’t opened a pull request yet. Add their GitHub username if you know it: their pull requests then count on this row instead of making a new one.</p><p>Everyone who opens a pull request is added automatically, named from their GitHub profile.</p>',
    },
    {
      chapter: 'People',
      title: 'Rename someone',
      target: 'form-rename',
      text: '<p>Show a real name instead of a GitHub username. Their pull requests still count, because the row keeps the username.</p>',
    },
    {
      chapter: 'People',
      title: 'One person, two rows',
      target: 'form-merge',
      text: '<p>If you added someone by name and they then opened a pull request under a username you didn’t give, they appear twice. <b>Merge</b> folds the duplicate into the row you keep, keeping the higher value of every column, so nobody loses points.</p>',
    },

    // ---------- 4. Mistakes ----------
    {
      chapter: 'Mistakes',
      title: 'Recent changes',
      target: 'history',
      text: '<p>Every facilitator change, by anyone, newest first, with who made it. Your practice changes are here too.</p>',
    },
    {
      chapter: 'Mistakes',
      title: 'Try it: undo',
      target: 'form-undo',
      text: '<p><b>Undo</b> reverses the top change under Recent changes, exactly the cells it changed, whoever made it. Press it again to go further back.</p><p>A cell someone has changed again since is left alone, and the result says so. Graded results are always kept.</p>',
    },

    // ---------- 5. Done ----------
    {
      chapter: 'Done',
      title: 'That’s it',
      stage: `
        <h2>You’re ready</h2>
        <ul class="checks">
          <li>The real page: ${page}</li>
          <li>The same forms are in the repository’s <b>Actions</b> tab, under <b>Facilitator:</b>.</li>
          <li>Pull requests are graded automatically within a minute; you only step in for what a check can’t judge.</li>
          <li>Practise again any time: <code>python3 facilitator_walkthrough.py</code>.</li>
        </ul>`,
      text: '<p>Close this tab and press <kbd>Ctrl</kbd>+<kbd>C</kbd> in the terminal to stop the practice copy.</p>',
    },
  ];
}
