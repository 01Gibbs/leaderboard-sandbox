// The facilitator walkthrough's content: one entry per step, shown by tour.js over the facilitator page
// (../facilitator.html?practice), which facilitator_walkthrough.py serves on a practice copy with made-up people.
// Steps work like steps.js: `target` is a data-tour name in facilitator.html, `stage` is HTML shown instead.
// "Try it" steps leave the page usable: the reader does it for real, on the practice copy.

export function steps(ctx) {
  const someone = ctx.people[0] || 'Asha Rao', other = ctx.people[1] || 'Ben Okafor';
  const page = ctx.pages_url ? `<a href="${ctx.pages_url}facilitator.html" target="_blank" rel="noopener">${ctx.pages_url}facilitator.html</a>` : 'the leaderboard’s address, followed by <code>facilitator.html</code>';
  return [
    // ---------- 1. The page ----------
    {
      chapter: 'The page',
      title: 'The facilitator page',
      stage: `
        <h2>Pick a person, then act</h2>
        <p class="lead">Everything a facilitator changes (points, results, names, duplicates, mistakes) starts from a person.
          This tour runs the page on a <b>practice copy</b> with made-up people, so try anything.</p>
        <div class="cards">
          <div class="card"><b>People</b><span>find someone, see where they stand</span></div>
          <div class="card"><b>Act</b><span>+1 help, +1 stretch, or More</span></div>
          <div class="card"><b>Changes</b><span>wait in one box until you send them all</span></div>
          <div class="card"><b>Undo</b><span>any one change, whenever</span></div>
        </div>
        <p class="hint">Use <kbd>→</kbd> and <kbd>←</kbd> or the buttons. On a step that says <b>Try it</b>, use the page itself.</p>`,
      text: `<p>The real page is at ${page}. The same changes can also be made from the repository’s Actions tab.</p>`,
    },
    {
      chapter: 'The page',
      title: 'This is a practice copy',
      target: 'practice',
      text: '<p>The banner says you are practising. Nothing here reaches GitHub or the real leaderboard; when you close the walkthrough, the practice copy is thrown away.</p>',
    },

    // ---------- 2. One person ----------
    {
      chapter: 'One person',
      title: 'Try it: find someone',
      target: 'roster',
      text: `<p>Everyone on the leaderboard, with their points and rank. Press <kbd>/</kbd> and start typing <b>${someone}</b> (a name or a GitHub username), then press <kbd>Enter</kbd>.</p>`,
    },
    {
      chapter: 'One person',
      title: 'Where they stand',
      target: 'person',
      text: '<p>Their points and rank, each exercise’s result, helps, stretch and bonus points, and the last few changes made to them. <b>Mark correct</b> sits next to any exercise that isn’t correct yet.</p>',
    },
    {
      chapter: 'One person',
      title: 'Try it: give a help',
      target: 'actions',
      text: `<p>Someone helped a colleague: press <b>+1 help</b> (or just <kbd>h</kbd>). <b>+1 stretch</b> is <kbd>s</kbd>.</p><p>Bonus points, taking points away, setting a result by hand, renaming and merging are under <b>More</b>.</p>`,
    },

    // ---------- 3. Changes ----------
    {
      chapter: 'Changes',
      title: 'Changes wait here',
      target: 'changes',
      text: '<p>Each change waits in this box, in words, so you can check it. Remove any you didn’t mean. Make as many as you like, for as many people as you like.</p>',
    },
    {
      chapter: 'Changes',
      title: 'Try it: send them',
      target: 'changes',
      text: '<p>Press <b>Send</b>. On the real page this opens GitHub with every waiting change filled in, in one tab: press <b>Submit new issue</b> there, once. Here, they are made straight away.</p><p>Each row shows <b>Done</b> and leaves the box, or <b>Not done</b> with the reason, for example a misspelt name.</p>',
    },
    {
      chapter: 'Changes',
      title: 'Undo just one change',
      target: 'history',
      text: '<p>Every change, by anyone, newest first. <b>Undo</b> next to one adds “Undo: …” to the Changes box; send it, and only that change is reversed. Later changes stay, and a cell someone changed again since is left alone.</p>',
    },

    // ---------- 4. Several people, and tidying up ----------
    {
      chapter: 'More',
      title: 'Several people at once',
      target: 'roster',
      text: `<p>Tick <b>Select several</b>, tick everyone who helped, and press <b>+1 help each</b>. One change per person waits in the box, and they all go together.</p>`,
    },
    {
      chapter: 'More',
      title: 'Someone new',
      target: 'roster',
      text: '<p>Type a name nobody has: <b>Add</b> appears under the list. Add their GitHub username if you know it, so their pull requests count on this row.</p><p>Everyone who opens a pull request is added automatically, named from their GitHub profile.</p>',
    },
    {
      chapter: 'More',
      title: 'Renaming, and one person twice',
      target: 'person',
      text: `<p><b>More → Rename…</b> shows a real name instead of a GitHub username. <b>More → Same person as…</b> folds a duplicate row into this one: it shows the row as it will be, keeping the higher value of every column, before you add it.</p>`,
    },

    // ---------- 5. Done ----------
    {
      chapter: 'Done',
      title: 'That’s it',
      stage: `
        <h2>You’re ready</h2>
        <ul class="checks">
          <li>The real page: ${page}</li>
          <li>Pick, act, send: one Submit on GitHub for everything you changed.</li>
          <li>Only the leaderboard’s collaborators can make changes; GitHub checks who submitted.</li>
          <li>Pull requests are graded automatically; you only step in for what a check can’t judge.</li>
          <li>Practise again any time: <code>python3 facilitator_walkthrough.py</code>.</li>
        </ul>`,
      text: `<p>Close this tab and press <kbd>Ctrl</kbd>+<kbd>C</kbd> in the terminal to stop the practice copy. ${other} and the others are made up, and gone when you do.</p>`,
    },
  ];
}
