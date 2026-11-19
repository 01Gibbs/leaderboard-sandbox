"""actions.js: what each facilitator action on the page asks for, without the page. Each action becomes the rows the
Changes box sends (and the words it shows), or a refusal saying why.

The rows are held to the grader: a batch of them, applied by leaderboard.py to the same participants.csv, is made
row for row, and the page refuses what the grader would refuse. Run in Node.js, with the page's scoring.js.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'grader'))
import exercise_tests  # noqa: E402
import leaderboard  # noqa: E402
import lessons  # noqa: E402

LESSONS = [{'key': 'fizzbuzz', 'label': 'FizzBuzz', 'repo': 'o/fizz', 'check': 'none'},
           {'key': 'rest_api', 'label': 'REST API', 'repo': 'o/rest', 'check': 'none'}]
CSV = '''name,github_username,fizzbuzz,rest_api,stretch,helped,bonus,pr_stretch
Asha Rao,asha-r,correct,,1,,,
Ben Okafor,,,submitted,,2,,
Cy Duo,"cy-one, cy-two",submitted,correct,,,3,
'''

# The scenario is JS run beside scoring.js and actions.js, given `act` (actions.js for the board), `who(name)` (a
# person) and `log` (what it returns).
_RUN = r'''
const fs = require('fs'), vm = require('vm');
const { scenario, csv, lessons } = JSON.parse(fs.readFileSync(0, 'utf8'));
const ctx = {}; vm.createContext(ctx);
for (const f of process.argv.slice(1)) vm.runInContext(fs.readFileSync(f, 'utf8'), ctx);
const people = vm.runInContext('readParticipants', ctx)(csv, lessons.map((l) => ({ k: l.key, label: l.label }))).rows;
ctx.act = vm.runInContext('facilitatorActions', ctx)({ people, lessons });
ctx.who = (name) => people.find((p) => p.name === name);
ctx.log = [];
vm.runInContext(`(() => { ${scenario} })()`, ctx);
process.stdout.write(JSON.stringify(ctx.log));
'''


def run(scenario, csv=CSV, lessons=LESSONS):
    r = subprocess.run(['node', '-e', _RUN, str(REPO / 'scoring.js'), str(REPO / 'actions.js')], capture_output=True, text=True,
                       timeout=60, input=json.dumps({'scenario': scenario, 'csv': csv, 'lessons': lessons}))
    if r.returncode:
        raise AssertionError('actions.js failed in Node:\n' + r.stderr)
    return json.loads(r.stdout)


def rows(results):
    """Every row the results ask the Changes box to send, in order."""
    return [c['args'] for r in results for c in r['changes']]


class Grader(unittest.TestCase):
    """A scratch leaderboard with CSV and LESSONS, for applying rows as the workflow does."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        (self.dir / 'grader').mkdir()
        (self.dir / 'lessons.json').write_text(json.dumps(LESSONS))
        (self.dir / 'participants.csv').write_text(CSV)

    def apply(self, batch_rows, batch_id='b1'):
        """What became of each row: [(ok, message)]."""
        leaderboard.run(['batch', batch_id, json.dumps(batch_rows)], self.dir) if batch_rows else None
        outcomes = json.loads((self.dir / 'grader' / 'batches.json').read_text())[batch_id]['rows']
        return [(o['ok'], o['message']) for o in outcomes]


@unittest.skipUnless(shutil.which('node'), 'needs Node.js to run actions.js')
class PersonActionTests(Grader):
    def test_a_person_is_named_by_their_login_or_by_name_when_they_have_none(self):
        out = run("log.push(act.award([who('Asha Rao'), who('Ben Okafor'), who('Cy Duo')], 'helped', 1));")
        self.assertEqual(rows(out), [['award', 'asha-r', 'helped', '1'], ['award', 'Ben Okafor', 'helped', '1'],
                                     ['award', 'cy-one', 'helped', '1']])
        self.assertEqual([c['text'] for c in out[0]['changes']],
                         ['Give 1 help to Asha Rao.', 'Give 1 help to Ben Okafor.', 'Give 1 help to Cy Duo.'])
        self.assertEqual([ok for ok, _ in self.apply(rows(out))], [True, True, True])

    def test_taking_away_more_than_someone_has_is_refused_as_the_grader_refuses_it(self):
        out = run("log.push(act.award([who('Asha Rao')], 'stretch', -2), act.award([who('Asha Rao')], 'bonus', -5),"
                  "act.award([who('Asha Rao')], 'stretch', 0));")
        self.assertEqual(out[0], {'error': 'Asha Rao has 1 stretch task; cannot take away 2.'})
        self.assertEqual(rows(out[1:2]), [['award', 'asha-r', 'bonus', '-5']])
        self.assertEqual(out[2], {'error': 'The amount must be a whole number other than 0.'})
        (refused, why), (made, _) = self.apply([['award', 'asha-r', 'stretch', '-2'], *rows(out[1:2])])
        self.assertEqual((refused, made), (False, True))
        self.assertIn('cannot take away 2', why)

    def test_rename_refuses_what_the_grader_refuses(self):
        names = ['Asha Rao', ' asha rao ', 'ASHA-R', '@cy-two', 'BEN OKAFOR', 'Benjamin Okafor']
        out = run(f"for (const n of {json.dumps(names)}) log.push(act.rename(who('Ben Okafor'), n));")
        self.assertEqual(out[0], {'error': 'Asha Rao is already on the board.'})
        self.assertEqual(out[-1]['changes'], [{'args': ['rename', 'Ben Okafor', 'Benjamin Okafor'], 'text': 'Show Ben Okafor as Benjamin Okafor.'}])
        page_ok = ['changes' in r for r in out]
        self.assertEqual(page_ok, [False, False, False, False, True, True])
        server_ok = [ok for ok, _ in self.apply([['rename', 'Ben Okafor', n] for n in names])]
        self.assertEqual(server_ok[:-1], page_ok[:-1])  # the last only fails because the one before renamed Ben

    def test_add_refuses_a_name_or_login_already_on_the_board_as_the_grader_does(self):
        tries = [['asha rao', ''], ['Dee New', '@CY-TWO'], ['', 'dee'], ['Dee New', '@dee']]
        out = run(f"for (const [n, gh] of {json.dumps(tries)}) log.push(act.add(n, gh));")
        self.assertEqual(out[:3], [{'error': 'asha rao is already on the board.'}, {'error': '@CY-TWO is already on the board.'},
                                   {'error': 'Give a name.'}])
        self.assertEqual(out[3]['changes'], [{'args': ['add', 'Dee New', 'dee'], 'text': 'Add Dee New (@dee).'}])
        self.assertEqual([ok for ok, _ in self.apply([['add', n, gh] for n, gh in tries])], [False, False, False, True])

    def test_the_merge_preview_is_what_the_grader_leaves(self):
        out = run("log.push(act.merge(who('Asha Rao'), who('Cy Duo')), act.mergePreview(who('Asha Rao'), who('Cy Duo')));")
        merged, preview = out
        self.assertEqual(merged['changes'], [{'args': ['merge', 'asha-r', 'cy-one'], 'text': 'Fold Cy Duo into Asha Rao.'}])
        self.assertEqual(preview, [['Name', 'Asha Rao', 'Cy Duo', 'Asha Rao'], ['GitHub', 'asha-r', 'cy-one cy-two', 'asha-r cy-one cy-two'],
                                   ['FizzBuzz', 'Correct', 'Submitted', 'Correct'], ['REST API', 'Not submitted', 'Correct', 'Correct'],
                                   ['Helps', 0, 0, 0], ['Stretch', 1, 0, 1], ['Bonus', 0, 3, 3]])
        self.assertEqual(self.apply(rows([merged]))[0][0], True)
        row = leaderboard.roster.Roster(self.dir).find('asha-r')
        labels = {'correct': 'Correct', 'submitted': 'Submitted', '': 'Not submitted'}
        self.assertEqual([[r[0], r[3]] for r in preview],
                         [['Name', row['name']], ['GitHub', row['github_username']], ['FizzBuzz', labels[row['fizzbuzz']]],
                          ['REST API', labels[row['rest_api']]], ['Helps', int(row['helped'] or 0)], ['Stretch', int(row['stretch'] or 0)],
                          ['Bonus', int(row['bonus'] or 0)]])

    def test_a_result_ranks_by_the_grader_s_ladder_not_its_points(self):
        out = run("RULES.points.submitted = 99; log.push(act.mergePreview(who('Asha Rao'), who('Cy Duo'))[2]);")
        self.assertEqual(out, [['FizzBuzz', 'Correct', 'Submitted', 'Correct']])

    def test_marking_a_result_and_undoing_it(self):
        out = run("log.push(act.mark(who('Cy Duo'), 'fizzbuzz', 'correct'), act.mark(who('Ben Okafor'), 'rest_api', 'none'));")
        self.assertEqual([c for r in out for c in r['changes']],
                         [{'args': ['mark', 'cy-one', 'fizzbuzz', 'correct'], 'text': "Mark Cy Duo's FizzBuzz as correct."},
                          {'args': ['mark', 'Ben Okafor', 'rest_api', 'none'], 'text': "Mark Ben Okafor's REST API as not submitted."}])
        self.assertEqual([ok for ok, _ in self.apply(rows(out))], [True, True])
        last = leaderboard.roster.Roster(self.dir).history()[-1]
        out = run(f"log.push(act.undo({json.dumps(last)}));")
        self.assertEqual(out[0]['changes'], [{'args': ['undo', last['id']], 'text': f'Undo: {last["action"]}'}])
        self.assertEqual(self.apply(rows(out), 'b2'), [(True, f'Undid: {last["action"]} (by {last["by"]} at {last["at"]})')])

    def test_rename_needs_a_different_name(self):
        out = run("log.push(act.rename(who('Ben Okafor'), '  '), act.rename(who('Ben Okafor'), 'Ben Okafor '));")
        self.assertEqual(out, [{'error': 'Give a different name.'}] * 2)


@unittest.skipUnless(shutil.which('node'), 'needs Node.js to run actions.js')
class LessonActionTests(Grader):
    FORM = {'repo': 'https://github.com/o/new-one', 'label': 'New one', 'key': 'new_one', 'check': 'tests', 'tests': ''}

    def add(self, *forms, pending='() => false'):
        return run(f"for (const f of {json.dumps(forms)}) log.push(act.addLesson(f, {pending}));")

    def test_a_lesson_from_the_form_is_the_row_the_grader_reads(self):
        out = self.add(self.FORM, {**self.FORM, 'tests': 'github.com/o/tests/tree/main/app/greeting', 'check': 'tests'})
        self.assertEqual(out[0]['changes'], [{'args': ['add-lesson', 'new_one', 'New one', 'o/new-one', 'tests', '', ''],
                                              'text': 'Add lesson New one (o/new-one, correct when its tests pass)'}])
        self.assertEqual(out[0]['look'], {'repo': 'o/new-one', 'check': 'tests', 'testsRepo': '', 'folder': ''})
        args = out[1]['changes'][0]['args']
        self.assertEqual(args[5:], ['o/tests', 'app/greeting'])
        a = leaderboard.parser(leaderboard.RowParser).parse_args(args)
        self.assertEqual((a.cmd, a.key, a.label, a.repo, a.check, a.tests_repo, a.tests_dir),
                         ('add-lesson', 'new_one', 'New one', 'o/new-one', 'tests', 'o/tests', 'app/greeting'))

    def test_a_column_name_or_repository_is_refused_as_the_grader_refuses_it(self):
        keys = ['stretch', 'name', 'github', 'pr_stretch', 'fizzbuzz', '1abc', 'New', 'new_one']
        out = self.add(*({**self.FORM, 'key': k} for k in keys), {**self.FORM, 'repo': 'O/FIZZ'})
        page_ok = ['changes' in r for r in out]
        server_ok = [not lessons.problems_adding(self.dir, {'key': k, 'label': 'New one', 'repo': 'o/new-one', 'check': 'tests'})
                     for k in keys] + [not lessons.problems_adding(self.dir, {'key': 'new_one', 'label': 'x', 'repo': 'O/FIZZ', 'check': 'tests'})]
        self.assertEqual(page_ok, server_ok)
        self.assertEqual(page_ok, [False] * 7 + [True, False])
        self.assertEqual(out[0]['problems'], ['The column name stretch is already used.'])
        self.assertEqual(out[-1]['problems'], ['O/FIZZ is already a lesson\'s repository.'])

    def test_a_lesson_waiting_in_changes_takes_its_column_and_repository(self):
        out = self.add(self.FORM, pending="(test) => test(['add-lesson', 'new_one', 'x', 'o/NEW-ONE', 'none', '', ''])")
        self.assertEqual(out[0]['problems'], ['The column name new_one is already used.', "o/new-one is already a lesson's repository."])

    def test_what_the_form_needs(self):
        out = self.add({'repo': 'o', 'label': '', 'key': '', 'check': 'tests', 'tests': 'not a repo'},
                       {**self.FORM, 'repo': 'o/new-one/sub'})
        self.assertEqual(out[0]['problems'], ['Give the exercise repository as owner/name, or its GitHub address.',
                                              'Give the name shown on the leaderboard.',
                                              'Give a column name: lowercase letters, digits and _ (the name shown has none to make one from).',
                                              "The tests repository is owner/name/folder, or its GitHub folder address; leave it empty for the exercise's own src/test/."])
        self.assertEqual(out[1]['problems'], ['The exercise is a whole repository: give owner/name, without a folder.'])

    def test_removing_a_lesson_and_trying_a_failed_one_again(self):
        lesson = {'key': 'fizzbuzz', 'label': 'FizzBuzz', 'repo': 'o/fizz', 'check': 'build', 'tests_repo': 'o/t', 'tests_dir': 'app'}
        out = run(f"const l = {json.dumps(lesson)}; log.push(act.removeLesson(l), act.tryLessonAgain(l));")
        self.assertEqual(out[0]['changes'], [{'args': ['remove-lesson', 'fizzbuzz'], 'text': 'Remove lesson FizzBuzz'}])
        self.assertEqual(rows(out[1:]), [['remove-lesson', 'fizzbuzz'], ['add-lesson', 'fizzbuzz', 'FizzBuzz', 'o/fizz', 'build', 'o/t', 'app']])

    def test_only_the_levels_the_grader_adds_a_lesson_with_are_offered(self):
        self.assertEqual(run("log.push(GENERIC);")[0], list(exercise_tests.GENERIC))

    def test_a_column_name_is_made_from_the_name_shown(self):
        out = run("log.push(['Replace a Library!', '2nd go', 'x'.repeat(60)].map(keyFrom));")
        self.assertEqual(out[0], ['replace_a_library', 'nd_go', 'x' * 40])


if __name__ == '__main__':
    unittest.main()
