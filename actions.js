// What each facilitator action on the page asks for, without the page: the rows the Changes box sends
// (leaderboard.py's commands, as `leaderboard.py batch` reads them) and the words it shows, or a refusal saying why.
//  - a person is named by their GitHub login, or by name when they have none, so a row always finds one row
//    (grader/roster.py's Sheet.find);
//  - each refusal here is one the grader would make too: grader/tests/test_actions.py holds the two to it.
// Every action returns { changes: [{ args, text }] } or { error }. The page draws them and decides nothing.
const UNITS = { helped: ['help', 'helps'], stretch: ['stretch task', 'stretch tasks'], bonus: ['bonus point', 'bonus points'] };
function plural(n, kind) { return `${Math.abs(n)} ${UNITS[kind][Math.abs(n) === 1 ? 0 : 1]}`; }
const handleOf = (p) => p.logins[0] || p.name;

// The levels a lesson can be added with (grader/exercise_tests.py GENERIC); any other check is code, added and
// removed through a pull request.
const GENERIC = ['none', 'build', 'tests'];
const CHECKED = { none: 'marked by hand', build: 'correct when it builds', tests: 'correct when its tests pass' };
// Columns a lesson cannot take (grader/lessons.py RESERVED).
const RESERVED = [...RULES.baseColumns, ...RULES.counts, RULES.earlyBonus.column, ...Object.keys(RULES.headerAliases)];
const keyFrom = (label) => label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^[^a-z]+/, '').slice(0, 40).replace(/_+$/, '');
// "owner/name[/folder]", or a GitHub address (github.com/owner/name[/tree/branch[/folder]], with or without https://):
// [owner/name, folder], or null. A file's address (/blob/) is not a folder. The default branch is always used.
function repoAndFolder(text) {
  const t = text.trim().replace(/^(https?:\/\/)?(www\.)?github\.com\//i, '').replace(/\.git$/, '').replace(/\/+$/, '');
  const m = t.match(/^([\w.-]+\/[\w.-]+)(?:\/tree\/[^/]+(?:\/(.+))?|\/(?!blob\/|tree\/)(.+))?$/);
  return m ? [m[1], m[2] || m[3] || ''] : null;
}
const addLessonArgs = (l) => ['add-lesson', l.key, l.label, l.repo, l.check, l.tests_repo || '', l.tests_dir || ''];

// `lessons`: the live ones, shown for each person; `allLessons`: those being checked too, whose columns and
// repositories are taken.
function facilitatorActions({ people, lessons, allLessons = lessons }) {
  const made = (...changes) => ({ changes: changes.map(([args, text]) => ({ args, text })) });
  // The person `q` finds, by name or GitHub login, ignoring case (as roster.py's Sheet.find), or undefined.
  function find(q) {
    const key = q.trim().toLowerCase();
    return people.find((p) => p.name.toLowerCase() === key || p.logins.some((l) => l.toLowerCase() === key.replace(/^@+/, '')));
  }

  function award(who, kind, amount) {
    if (!Number.isInteger(amount) || amount === 0) return { error: 'The amount must be a whole number other than 0.' };
    for (const p of who) {
      if (amount < 0 && kind !== 'bonus' && (p[kind] || 0) + amount < 0) return { error: `${p.name} has ${plural(p[kind] || 0, kind)}; cannot take away ${-amount}.` };
    }
    return made(...who.map((p) => [['award', handleOf(p), kind, String(amount)],
      `${amount < 0 ? 'Take' : 'Give'} ${plural(amount, kind)} ${amount < 0 ? 'from' : 'to'} ${p.name}.`]));
  }

  function rename(p, name) {
    name = name.trim();
    if (!name || name === p.name) return { error: 'Give a different name.' };
    const taken = find(name);
    if (taken && taken !== p) return { error: `${name} is already on the board.` };
    return made([['rename', handleOf(p), name], `Show ${p.name} as ${name}.`]);
  }

  function add(name, github) {
    name = name.trim(); github = github.trim().replace(/^@+/, '');
    if (!name) return { error: 'Give a name.' };
    if (find(name)) return { error: `${name} is already on the board.` };
    if (github && find(github)) return { error: `@${github} is already on the board.` };
    return made([['add', name, github], `Add ${name}${github ? ' (@' + github + ')' : ''}.`]);
  }

  function mark(p, key, status) {
    const l = lessons.find((x) => x.key === key);
    return made([['mark', handleOf(p), key, status], `Mark ${p.name}'s ${l.label} as ${RULES.labels[status].toLowerCase()}.`]);
  }

  function undo(h) { return made([['undo', h.id], `Undo: ${h.action}`]); }

  function merge(keep, drop) {
    return made([['merge', handleOf(keep), handleOf(drop)], `Fold ${drop.name} into ${keep.name}.`]);
  }

  // What merge leaves, as roster.py's merge makes it: the kept row's name, both rows' GitHub usernames, and the
  // higher of every result (by RULES.statusOrder) and count. [[what, keep, duplicate, afterwards]].
  function mergePreview(keep, drop) {
    const rank = (s) => RULES.statusOrder.indexOf(s);
    const github = (p) => p.logins.join(' ') || '–';
    return [['Name', keep.name, drop.name, keep.name],
      ['GitHub', github(keep), github(drop), [...new Set([...keep.logins, ...drop.logins])].join(' ') || '–'],
      ...lessons.map((l) => {
        const a = keep.tracks[l.key], b = drop.tracks[l.key];
        return [l.label, RULES.labels[a], RULES.labels[b], RULES.labels[rank(b) > rank(a) ? b : a]];
      }),
      ...[['Helps', 'helped'], ['Stretch', 'stretch'], ['Bonus', 'bonus']].map(([k, f]) => [k, keep[f], drop[f], Math.max(keep[f], drop[f])])];
  }

  // The Add a lesson form ({ repo, label, key, check, tests }: tests empty for the exercise's own src/test/), with
  // `pending(test)` saying whether a waiting change passes `test`: { problems } or { changes, look }, where `look` is
  // what to check on GitHub before it is added (the page's reads; GitHub checks all of it again before saving).
  function addLesson(form, pending) {
    const where = repoAndFolder(form.repo), label = form.label.trim(), key = form.key.trim(), check = form.check;
    const elsewhere = check === 'tests' && form.tests.trim() !== '', tests = elsewhere ? repoAndFolder(form.tests) : null;
    const adding = (test) => pending((a) => a[0] === 'add-lesson' && test(a));
    const problems = [];
    if (!where) problems.push('Give the exercise repository as owner/name, or its GitHub address.');
    else if (where[1]) problems.push('The exercise is a whole repository: give owner/name, without a folder.');
    if (!label) problems.push('Give the name shown on the leaderboard.');
    if (!key) problems.push('Give a column name: lowercase letters, digits and _ (the name shown has none to make one from).');
    else if (!/^[a-z][a-z0-9_]*$/.test(key)) problems.push('The column name must be lowercase letters, digits and _, starting with a letter.');
    else if (RESERVED.includes(key) || allLessons.some((l) => l.key === key) || adding((a) => a[1] === key)) problems.push(`The column name ${key} is already used.`);
    const repo = where && where[0].toLowerCase();
    if (where && (allLessons.some((l) => l.repo.toLowerCase() === repo) || adding((a) => a[3].toLowerCase() === repo))) problems.push(`${where[0]} is already a lesson's repository.`);
    if (elsewhere && !tests) problems.push('The tests repository is owner/name/folder, or its GitHub folder address; leave it empty for the exercise\'s own src/test/.');
    if (problems.length) return { problems };
    const lesson = { key, label, repo: where[0], check, tests_repo: tests ? tests[0] : '', tests_dir: tests ? tests[1] : '' };
    return { ...made([addLessonArgs(lesson), `Add lesson ${label} (${where[0]}, ${CHECKED[check]})`]),
             look: { repo: where[0], check, testsRepo: lesson.tests_repo, folder: lesson.tests_dir } };
  }

  const removeLesson = (l) => made([['remove-lesson', l.key], `Remove lesson ${l.label}`]);
  // A lesson that failed its trial, removed and added again in one Send, so it is tried afresh.
  const tryLessonAgain = (l) => made([['remove-lesson', l.key], `Remove lesson ${l.label}`], [addLessonArgs(l), `Add lesson ${l.label} again`]);

  return { find, add, award, mark, rename, merge, mergePreview, undo, addLesson, removeLesson, tryLessonAgain };
}
