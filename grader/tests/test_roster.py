"""The roster: facilitator actions, undo, and applying graded results, driven through the command line.

Run: python3 -m unittest discover grader/tests
Each test points the command line at its own scratch copy of the repository (participants.csv, lessons.json,
grader/results.json, grader/history.json), never the real one.
"""
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

GRADER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRADER))
import leaderboard  # noqa: E402
import roster  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import page  # noqa: E402

LESSONS = [
    {'key': 'fizzbuzz', 'label': 'FizzBuzz', 'repo': 'o/fizz', 'check': 'fizzbuzz'},
    {'key': 'rest_api', 'label': 'REST API', 'repo': 'o/rest', 'check': 'rest_api'},
    {'key': 'manual', 'label': 'Manual', 'repo': 'o/manual', 'check': 'none'},
]
CSV = '''name,github_username,fizzbuzz,rest_api,manual,stretch,helped,bonus,pr_stretch
Stuart Smith,StuartJSmith10-dev,correct,,,1,,,
Bukky Adeyemi,,,,,2,1,,
bukkie-create,bukkie-create,submitted,submitted,,,3,,
'''


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        (self.dir / 'grader').mkdir()
        (self.dir / 'lessons.json').write_text(json.dumps(LESSONS))
        (self.dir / 'participants.csv').write_text(CSV)

    def patch(self, obj, name, value):
        old = getattr(obj, name)
        setattr(obj, name, value)
        self.addCleanup(setattr, obj, name, old)

    def cli(self, *argv):
        """Run a command the way a terminal or workflow does. Returns (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = leaderboard.main(list(argv), root=self.dir)
        return code, out.getvalue(), err.getvalue()

    def csv_text(self):
        return (self.dir / 'participants.csv').read_text()

    def roster(self):
        return roster.Roster(self.dir)

    def row(self, who):
        return self.roster().find(who)

    def results(self, *subs):
        """Each submission: (login, lesson, passed[, profile name]). They were opened in the order given."""
        people = {s[0]: s[3] if len(s) > 3 else s[0] for s in subs}
        data = {'people': people, 'submissions': {
            f'o/{s[1]}#{i}': {'login': s[0], 'task': s[1], 'passed': s[2], 'created_at': f'2026-11-01T00:00:{i:02d}Z'}
            for i, s in enumerate(subs)}}
        (self.dir / 'grader' / 'results.json').write_text(json.dumps(data))


class AwardTests(Sandbox):
    def test_award_adds_to_existing_count(self):
        code, out, _ = self.cli('award', 'Stuart Smith', 'stretch', '2')
        self.assertEqual(code, 0)
        self.assertEqual(self.row('Stuart Smith')['stretch'], '3')
        self.assertIn('Gave 2 stretch tasks to Stuart Smith (stretch: 1 -> 3)', out)

    def test_award_defaults_to_one_and_matches_login_case_insensitively(self):
        self.cli('award', '@stuartjsmith10-DEV', 'helped')
        self.assertEqual(self.row('Stuart Smith')['helped'], '1')

    def test_bonus_points_can_go_negative(self):
        self.cli('award', 'Stuart Smith', 'bonus', '5')
        self.cli('award', 'Stuart Smith', 'bonus', '-8')
        self.assertEqual(self.row('Stuart Smith')['bonus'], '-3')

    def test_counts_cannot_go_below_zero(self):
        code, _, err = self.cli('award', 'Stuart Smith', 'stretch', '-2')
        self.assertEqual(code, 1)
        self.assertIn('cannot take away 2', err)
        self.assertEqual(self.csv_text(), CSV)

    def test_zero_or_text_amount_is_rejected(self):
        for amount in ('0', 'lots'):
            code, _, err = self.cli('award', 'Stuart Smith', 'bonus', amount)
            self.assertEqual(code, 1)
            self.assertIn('whole number', err)
        self.assertEqual(self.csv_text(), CSV)

    def test_unknown_person_suggests_close_names_and_changes_nothing(self):
        code, _, err = self.cli('award', 'Stuart Smit', 'helped')
        self.assertEqual(code, 1)
        self.assertIn("Did you mean 'Stuart Smith'", err)
        self.assertEqual(self.csv_text(), CSV)
        self.assertEqual(self.roster().history(), [])


class MarkRenameAddTests(Sandbox):
    def test_mark_sets_status(self):
        code, out, _ = self.cli('mark', 'Stuart Smith', 'manual', 'correct')
        self.assertEqual(code, 0)
        self.assertEqual(self.row('Stuart Smith')['manual'], 'correct')

    def test_mark_lower_warns_grader_may_raise_again(self):
        _, out, _ = self.cli('mark', 'Stuart Smith', 'fizzbuzz', 'none')
        self.assertEqual(self.row('Stuart Smith')['fizzbuzz'], '')
        self.assertIn('never lowers', out)

    def test_mark_cannot_lower_what_a_pull_request_earned(self):
        self.results(('StuartJSmith10-dev', 'fizzbuzz', True))
        code, _, err = self.cli('mark', 'Stuart Smith', 'fizzbuzz', 'submitted')
        self.assertEqual(code, 1)
        self.assertIn('pull request', err)
        self.assertEqual(self.csv_text(), CSV)

    def test_mark_unknown_lesson_lists_valid_ones(self):
        code, _, err = self.cli('mark', 'Stuart Smith', 'docker', 'correct')
        self.assertEqual(code, 1)
        self.assertIn('fizzbuzz, rest_api, manual', err)

    def test_rename_keeps_github_so_grader_still_matches(self):
        self.cli('rename', 'bukkie-create', 'Bukola A')
        self.assertEqual(self.row('bukkie-create')['name'], 'Bukola A')

    def test_add_person_and_reject_duplicates(self):
        self.assertEqual(self.cli('add', 'New Person', '@newbie')[0], 0)
        self.assertEqual(self.row('newbie')['name'], 'New Person')
        code, _, err = self.cli('add', 'Someone Else', 'NEWBIE')
        self.assertEqual(code, 1)
        self.assertIn('already on the leaderboard as New Person', err)

    def test_add_refuses_a_name_already_on_the_board(self):
        code, _, err = self.cli('add', 'stuart smith', 'other-stuart')
        self.assertEqual(code, 1)
        self.assertIn('already on the leaderboard', err)

    def test_add_refuses_a_name_that_is_already_ambiguous(self):
        self.results(('other-stuart', 'rest_api', False, 'Stuart Smith'))
        self.cli('apply')
        code, _, err = self.cli('add', 'Stuart Smith')
        self.assertEqual(code, 1)
        self.assertIn('More than one row matches', err)
        self.assertEqual(sum(r['name'] == 'Stuart Smith' for r in self.roster().rows()), 2)

    def test_ambiguous_name_asks_for_login(self):
        # Two people can share a name when the grader adds someone whose GitHub profile name matches.
        self.results(('other-stuart', 'rest_api', False, 'Stuart Smith'))
        self.cli('apply')
        code, _, err = self.cli('award', 'Stuart Smith', 'helped')
        self.assertEqual(code, 1)
        self.assertIn('More than one row matches', err)
        self.assertEqual(self.cli('award', 'other-stuart', 'helped')[0], 0)


class MergeTests(Sandbox):
    def test_merge_keeps_the_higher_value_of_every_column(self):
        code, out, _ = self.cli('merge', 'Bukky Adeyemi', 'bukkie-create')
        self.assertEqual(code, 0)
        r = self.roster()
        self.assertEqual(len(r.rows()), 2)
        row = r.find('Bukky Adeyemi')
        self.assertEqual((row['github_username'], row['fizzbuzz'], row['rest_api'], row['stretch'], row['helped']),
                         ('bukkie-create', 'submitted', 'submitted', '2', '3'))

    def test_merged_row_is_not_recreated_by_the_grader(self):
        self.results(('bukkie-create', 'fizzbuzz', True))
        self.cli('merge', 'Bukky Adeyemi', 'bukkie-create')
        self.cli('apply')
        rows = self.roster().rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(self.roster().find('Bukky Adeyemi')['fizzbuzz'], 'correct')

    @page.needs_node
    def test_merged_person_never_has_fewer_points_than_either_row(self):
        keys = [l['key'] for l in LESSONS]
        points = lambda: page.points(self.csv_text(), keys)
        before = points()
        self.cli('merge', 'Bukky Adeyemi', 'bukkie-create')
        after = points()['Bukky Adeyemi']
        self.assertGreaterEqual(after, max(before['Bukky Adeyemi'], before['bukkie-create']))
        self.assertEqual(after, 10 + 10 + 2 * 5 + 3 * 5)  # submitted twice, 2 stretch, 3 helps

    def test_two_github_accounts_on_one_row_both_count(self):
        self.cli('add', 'Alt', 'second-account')
        self.cli('merge', 'Bukky Adeyemi', 'bukkie-create', 'second-account')
        self.assertEqual(self.row('second-account')['github_username'], 'bukkie-create second-account')
        self.results(('second-account', 'rest_api', True))
        self.cli('apply')
        self.assertEqual(self.row('Bukky Adeyemi')['rest_api'], 'correct')

    def test_same_duplicate_named_twice_is_refused_cleanly(self):
        code, _, err = self.cli('merge', 'Stuart Smith', 'bukkie-create', '@BUKKIE-CREATE')
        self.assertEqual(code, 1)
        self.assertIn('already being merged', err)

    def test_cannot_merge_into_itself(self):
        code, _, err = self.cli('merge', 'bukkie-create', 'bukkie-create')
        self.assertEqual(code, 1)
        self.assertIn('into itself', err)


class UndoOneChangeTests(Sandbox):
    """Each change has an id, and `undo <id>` reverses just that change, whenever it was made."""

    def ids(self):
        return [h['id'] for h in self.roster().history()]

    def test_every_change_gets_its_own_id(self):
        self.cli('award', 'Stuart Smith', 'helped')
        self.cli('award', 'Bukky Adeyemi', 'stretch')
        ids = self.ids()
        self.assertEqual(len(set(ids)), 2)
        self.assertTrue(all(isinstance(i, str) and i for i in ids))

    def test_undoing_an_earlier_change_leaves_later_ones(self):
        self.cli('award', 'Stuart Smith', 'helped', '2')
        self.cli('award', 'Bukky Adeyemi', 'stretch', '3')
        first, second = self.ids()
        code, out, _ = self.cli('undo', first)
        self.assertEqual(code, 0)
        self.assertIn('Undid: Gave 2 helps to Stuart Smith', out)
        self.assertEqual((self.row('Stuart Smith')['helped'], self.row('Bukky Adeyemi')['stretch']), ('', '5'))
        self.assertEqual(self.ids(), [second])

    def test_the_same_change_cannot_be_undone_twice(self):
        self.cli('award', 'Stuart Smith', 'helped')
        (only,) = self.ids()
        self.cli('undo', only)
        before = self.csv_text()
        code, _, err = self.cli('undo', only)
        self.assertEqual(code, 1)
        self.assertIn(f'No change {only} to undo', err)
        self.assertEqual(self.csv_text(), before)

    def test_a_cell_changed_again_since_is_kept_and_reported(self):
        self.cli('award', 'Stuart Smith', 'helped', '2')
        self.cli('award', 'Stuart Smith', 'helped', '1')
        first, _ = self.ids()
        code, out, _ = self.cli('undo', first)
        self.assertEqual(code, 0)
        self.assertIn("Stuart Smith's helped was changed again since, so it stays 3", out)
        self.assertEqual(self.row('Stuart Smith')['helped'], '3')

    def test_an_add_is_not_undone_once_a_facilitator_changed_that_person(self):
        self.cli('add', 'Pat Lee', 'patlee')
        added = self.ids()[0]
        self.cli('award', 'Pat Lee', 'helped')
        before = self.csv_text()
        code, _, err = self.cli('undo', added)
        self.assertEqual(code, 1)
        self.assertIn('Pat Lee has been changed since they were added', err)
        self.assertEqual(self.csv_text(), before)

    def test_an_add_is_not_undone_once_the_person_has_graded_pull_requests(self):
        # The grader would add them straight back from their results.
        self.cli('add', 'Pat Lee', 'patlee')
        added = self.ids()[0]
        self.results(('patlee', 'manual', None))
        self.cli('apply')
        code, _, err = self.cli('undo', added)
        self.assertEqual(code, 1)
        self.assertIn('pull request', err)
        self.assertIn('Pat Lee', self.csv_text())

    def test_an_add_without_pull_requests_is_undone(self):
        self.cli('add', 'Pat Lee', 'patlee')
        self.assertEqual(self.cli('undo', self.ids()[0])[0], 0)
        self.assertNotIn('Pat Lee', self.csv_text())

    def test_ids_are_short_enough_to_read_and_type(self):
        self.cli('award', 'Stuart Smith', 'helped')
        self.assertRegex(self.ids()[0], r'^c[0-9a-f]{6}$')

    def test_an_award_is_undone_after_a_merge_gave_the_person_another_username(self):
        self.cli('award', 'Bukky Adeyemi', 'stretch', '2')
        award = self.ids()[0]
        self.cli('merge', 'Bukky Adeyemi', 'bukkie-create')  # her row now has a username too
        code, _, err = self.cli('undo', award)
        self.assertEqual(code, 0, err)
        self.assertEqual(self.row('Bukky Adeyemi')['stretch'], '2')

    def test_a_merge_is_not_undone_once_its_row_was_merged_again(self):
        self.cli('merge', 'Bukky Adeyemi', 'bukkie-create')
        first = self.ids()[0]
        self.cli('merge', 'Stuart Smith', 'Bukky Adeyemi')
        before = self.csv_text()
        code, _, err = self.cli('undo', first)
        self.assertEqual(code, 1)
        self.assertIn('merged', err)
        self.assertEqual(self.csv_text(), before)

    def test_an_add_is_not_undone_once_a_facilitator_marked_a_result(self):
        self.cli('add', 'Pat Lee', 'patlee')
        added = self.ids()[0]
        self.cli('mark', 'Pat Lee', 'manual', 'correct')
        before = self.csv_text()
        code, _, err = self.cli('undo', added)
        self.assertEqual(code, 1)
        self.assertIn('manual', err)
        self.assertEqual(self.csv_text(), before)

    def test_an_add_that_cannot_be_found_any_more_is_not_dropped_from_history(self):
        self.cli('add', 'No Login')
        added = self.ids()[0]
        self.cli('rename', 'No Login', 'Renamed Person')
        code, _, err = self.cli('undo', added)
        self.assertEqual(code, 1)
        self.assertIn('No Login', err)
        self.assertIn(added, self.ids(), 'still in history, so it can be undone once the rename is')

    def test_plain_undo_still_reverses_the_latest(self):
        self.cli('award', 'Stuart Smith', 'helped')
        self.cli('award', 'Bukky Adeyemi', 'helped')
        self.cli('undo')
        self.assertEqual(self.row('Bukky Adeyemi')['helped'], '1')  # back to what it was
        self.assertEqual(len(self.ids()), 1)

    def test_changes_from_before_ids_get_one_when_history_is_next_written(self):
        self.cli('award', 'Stuart Smith', 'helped')
        history = json.loads((self.dir / 'grader' / 'history.json').read_text())
        del history[0]['id']
        (self.dir / 'grader' / 'history.json').write_text(json.dumps(history))
        self.cli('award', 'Bukky Adeyemi', 'helped')
        ids = self.ids()
        self.assertEqual(len(set(ids)), 2)


class BatchTests(Sandbox):
    """Several changes in one go, as the facilitator page sends them: each row on its own, each undoable."""

    def batch(self, batch_id, *rows):
        return self.cli('batch', batch_id, json.dumps([list(r) for r in rows]))

    def outcomes(self, batch_id):
        return json.loads((self.dir / 'grader' / 'batches.json').read_text())[batch_id]['rows']

    def test_each_row_is_applied_and_recorded(self):
        code, out, _ = self.batch('b1', ('award', 'Stuart Smith', 'helped', '1'), ('award', 'Bukky Adeyemi', 'stretch', '2'),
                                  ('rename', 'bukkie-create', 'Bukola A'))
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith('3 of 3 changes made'), out)
        self.assertEqual((self.row('Stuart Smith')['helped'], self.row('Bukky Adeyemi')['stretch'], self.row('bukkie-create')['name']),
                         ('1', '4', 'Bukola A'))
        history = self.roster().history()
        self.assertEqual([(h['batch'], h['row']) for h in history], [('b1', 1), ('b1', 2), ('b1', 3)])
        rows = self.outcomes('b1')
        self.assertEqual([r['ok'] for r in rows], [True, True, True])
        self.assertEqual([r['change'] for r in rows], [h['id'] for h in history])
        self.assertIn('Gave 1 help to Stuart Smith', rows[0]['message'])

    def test_a_refused_row_does_not_stop_the_others(self):
        code, out, _ = self.batch('b2', ('award', 'Nobody Here', 'helped', '1'), ('award', 'Stuart Smith', 'helped', '1'))
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith('1 of 2 changes made'), out)
        self.assertIn('❌ Nobody called "Nobody Here"', out)
        rows = self.outcomes('b2')
        self.assertEqual([r['ok'] for r in rows], [False, True])
        self.assertIsNone(rows[0]['change'])
        self.assertEqual(len(self.roster().history()), 1)

    def test_every_row_refused_changes_nothing_but_records_why(self):
        # Exit 0, so the workflow saves batches.json and the page can show why; the run page still says ❌.
        code, _, err = self.batch('b3', ('award', 'Nobody Here', 'helped', '1'))
        self.assertEqual(code, 0)
        self.assertIn('Nothing was changed', err)
        self.assertEqual(self.csv_text(), CSV)
        self.assertEqual([r['ok'] for r in self.outcomes('b3')], [False])  # the page still learns why

    def test_one_row_of_a_batch_is_undone_on_its_own(self):
        self.batch('b4', ('award', 'Stuart Smith', 'helped', '1'), ('award', 'Bukky Adeyemi', 'helped', '1'))
        stuart, bukky = (r['change'] for r in self.outcomes('b4'))
        code, out, _ = self.batch('b5', ('undo', stuart))
        self.assertEqual(code, 0)
        self.assertEqual((self.row('Stuart Smith')['helped'], self.row('Bukky Adeyemi')['helped']), ('', '2'))
        self.assertEqual([h['id'] for h in self.roster().history()], [bukky])

    def test_a_batch_is_applied_once(self):
        self.batch('b6', ('award', 'Stuart Smith', 'helped', '1'))
        code, _, err = self.batch('b6', ('award', 'Stuart Smith', 'helped', '1'))
        self.assertEqual(code, 1)
        self.assertIn('Batch b6 was applied already', err)
        self.assertEqual(self.row('Stuart Smith')['helped'], '1')

    def test_only_facilitator_changes_go_in_a_batch(self):
        for row in (('grade',), ('apply',), ('batch', 'x', '[]'), ('history',), ('pin-tests', 'fizzbuzz')):
            with self.subTest(row[0]):
                code, _, err = self.batch(f'bad-{row[0]}', row)
                self.assertEqual(code, 0)  # refused as a whole, and why is saved for the page
                self.assertIn('cannot go in a batch', err)
                self.assertIn('cannot go in a batch', json.loads((self.dir / 'grader' / 'batches.json').read_text())[f'bad-{row[0]}']['error'])
        self.assertEqual(self.csv_text(), CSV)

    def test_a_batch_refused_as_a_whole_still_says_why_for_the_page(self):
        for rows, reason in (('not json', 'not a JSON list'), ('[["grade"]]', 'cannot go in a batch')):
            with self.subTest(rows):
                batch_id = 'whole-' + str(abs(hash(rows)))[:6]
                code, out, err = self.cli('batch', batch_id, rows)
                self.assertEqual(code, 0, 'exit 0, so the workflow saves batches.json')
                record = json.loads((self.dir / 'grader' / 'batches.json').read_text())[batch_id]
                self.assertIn(reason, record['error'])
                self.assertTrue(out.strip(), 'a first line for the commit title')
        self.assertEqual(self.csv_text(), CSV)

    def test_a_row_with_bad_arguments_says_what_is_wrong(self):
        code, out, _ = self.batch('args1', ('award', 'Stuart Smith', 'gold'), ('award', '-h'), ('award', 'Stuart Smith', 'helped'))
        self.assertEqual(code, 0)
        rows = self.outcomes('args1')
        self.assertEqual([r['ok'] for r in rows], [False, False, True])
        self.assertIn("invalid choice: 'gold'", rows[0]['message'])
        self.assertNotIn('usage:', out)  # no help text, so it cannot become a commit title
        self.assertTrue(out.startswith('1 of 3 changes made'), out)

    def test_every_row_refused_still_gives_a_commit_title(self):
        code, out, _ = self.batch('title1', ('award', 'Nobody Here', 'helped', '1'))
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith('Nothing was changed. 0 of 1 changes made'), out)

    def test_a_malformed_batch_changes_nothing(self):
        for batch_id, rows, code in (('ok-1', 'not json', 0), ('ok-2', '{"award": 1}', 0), ('bad id!', '[["undo"]]', 1)):
            with self.subTest(rows=rows, batch_id=batch_id):
                self.assertEqual(self.cli('batch', batch_id, rows)[0], code)  # a bad id cannot be recorded: exit 1
        self.assertEqual(self.csv_text(), CSV)


class UndoTests(Sandbox):
    def test_undo_reverses_actions_one_at_a_time(self):
        self.cli('award', 'Stuart Smith', 'helped', '2')
        after_first = self.csv_text()
        self.cli('merge', 'Bukky Adeyemi', 'bukkie-create')
        code, out, _ = self.cli('undo')
        self.assertEqual(code, 0)
        self.assertIn('Undid: Merged bukkie-create into Bukky Adeyemi', out)
        self.assertEqual(self.csv_text(), after_first)
        self.cli('undo')
        self.assertEqual(self.csv_text(), CSV)
        code, _, err = self.cli('undo')
        self.assertEqual(code, 1)
        self.assertIn('nothing to undo', err)

    def test_undo_keeps_grader_results_that_arrived_after_the_action(self):
        self.cli('rename', 'Stuart Smith', 'Stu')
        self.results(('newcomer', 'rest_api', True, 'New Comer'))
        self.cli('apply')
        self.cli('undo')
        r = self.roster()
        self.assertEqual(r.find('Stuart Smith')['name'], 'Stuart Smith')
        self.assertEqual(r.find('newcomer')['rest_api'], 'correct')

    def test_undo_keeps_edits_made_directly_to_the_csv_since(self):
        self.cli('award', 'Stuart Smith', 'helped', '2')
        edited = self.csv_text().replace('Bukky Adeyemi,,,,,2,1,', 'Bukky Adeyemi,,,,,5,1,')  # the lead edits the file on GitHub
        (self.dir / 'participants.csv').write_text(edited)
        self.cli('undo')
        self.assertEqual(self.row('Stuart Smith')['helped'], '')
        self.assertEqual(self.row('Bukky Adeyemi')['stretch'], '5')

    def test_undo_leaves_a_cell_changed_again_since_and_says_so(self):
        self.cli('award', 'Stuart Smith', 'helped', '2')
        (self.dir / 'participants.csv').write_text(self.csv_text().replace('correct,,,1,2,', 'correct,,,1,4,'))
        code, out, _ = self.cli('undo')
        self.assertEqual(code, 0)
        self.assertEqual(self.row('Stuart Smith')['helped'], '4')
        self.assertIn("Kept: Stuart Smith's helped was changed again since, so it stays 4", out)

    def test_undo_merge_restores_both_rows_exactly(self):
        self.cli('merge', 'Bukky Adeyemi', 'bukkie-create')
        self.cli('undo')
        self.assertEqual(self.csv_text().splitlines()[1:], CSV.splitlines()[1:])

    def test_undo_add_removes_the_person_again(self):
        self.cli('add', 'New Person')
        self.cli('award', 'New Person', 'helped')
        self.cli('undo')
        self.cli('undo')
        self.assertEqual(self.csv_text(), CSV)

    def test_undo_rename_of_someone_without_github(self):
        self.cli('rename', 'Bukky Adeyemi', 'Bukola Adeyemi')
        self.cli('undo')
        self.assertEqual(self.row('Bukky Adeyemi')['stretch'], '2')

    def test_history_lists_newest_first_with_who(self):
        self.patch(roster, 'actor', lambda: 'facilitator-1')
        self.cli('award', 'Stuart Smith', 'helped')
        self.cli('rename', 'Stuart Smith', 'Stu')
        _, out, _ = self.cli('history')
        lines = out.strip().splitlines()
        self.assertIn('facilitator-1: Renamed Stuart Smith to Stu', lines[0])
        self.assertIn('Gave 1 help to Stuart Smith', lines[1])

    def test_history_is_capped(self):
        self.patch(roster, 'HISTORY_LIMIT', 3)
        for _ in range(5):
            self.cli('award', 'Stuart Smith', 'bonus')
        self.assertEqual(len(self.roster().history()), 3)


class GradedResultsAlwaysHoldTests(Sandbox):
    """Whatever a facilitator does, the board afterwards includes every graded result: nobody has to remember
    to apply them."""

    def test_every_action_brings_in_results_graded_since(self):
        self.results(('newcomer', 'rest_api', True, 'New Comer'), ('StuartJSmith10-dev', 'rest_api', False))
        for action in (('award', 'Stuart Smith', 'helped'), ('rename', 'Stuart Smith', 'Stu'), ('add', 'Pat', 'pat'),
                       ('mark', 'bukkie-create', 'manual', 'correct')):
            with self.subTest(action[0]):
                (self.dir / 'participants.csv').write_text(CSV)
                self.assertEqual(self.cli(*action)[0], 0)
                self.assertEqual(self.row('newcomer')['rest_api'], 'correct')
                self.assertEqual(self.row('StuartJSmith10-dev')['rest_api'], 'submitted')
                self.assertEqual(self.row('newcomer')['pr_stretch'], '1')

    def test_undoing_an_action_keeps_graded_results(self):
        self.cli('add', 'Pat', 'newcomer')
        self.results(('newcomer', 'rest_api', True))
        self.cli('award', 'Pat', 'helped')
        self.cli('undo')
        self.assertEqual((self.row('newcomer')['helped'], self.row('newcomer')['rest_api']), ('', 'correct'))

    def test_undo_does_not_take_back_what_the_grader_added(self):
        self.results(('newcomer', 'rest_api', True))
        self.cli('award', 'Stuart Smith', 'helped')
        self.cli('undo')
        self.assertEqual(self.row('newcomer')['rest_api'], 'correct')
        self.assertEqual(self.row('Stuart Smith')['helped'], '')

    def test_apply_takes_the_grading_jobs_results_file(self):
        graded = self.dir / 'graded.json'
        self.results(('newcomer', 'rest_api', True))
        (self.dir / 'grader' / 'results.json').rename(graded)
        self.assertEqual(self.cli('apply', str(graded))[0], 0)
        self.assertEqual(self.row('newcomer')['rest_api'], 'correct')
        self.assertEqual(json.loads((self.dir / 'grader' / 'results.json').read_text()), json.loads(graded.read_text()))


class ApplyTests(Sandbox):
    def test_new_github_account_gets_a_row_named_from_profile(self):
        self.results(('newbie', 'rest_api', False, 'Newbie Person'))
        self.cli('apply')
        row = self.row('newbie')
        self.assertEqual((row['name'], row['rest_api']), ('Newbie Person', 'submitted'))

    def test_a_row_named_by_login_takes_the_profile_name_once_known(self):
        self.results(('newbie', 'rest_api', False))  # profile not known yet: the row is named newbie
        self.cli('apply')
        self.results(('newbie', 'rest_api', False, 'Newbie Person'), ('renamed', 'rest_api', False, 'Profile Name'))
        self.cli('apply')
        self.cli('rename', 'renamed', 'Chosen By Facilitator')
        self.cli('apply')
        self.assertEqual(self.row('newbie')['name'], 'Newbie Person')
        self.assertEqual(self.row('renamed')['name'], 'Chosen By Facilitator')

    def test_never_lowers_a_status(self):
        self.results(('StuartJSmith10-dev', 'fizzbuzz', False))
        self.cli('apply')
        self.assertEqual(self.row('Stuart Smith')['fizzbuzz'], 'correct')

    def test_best_result_across_several_pull_requests_wins(self):
        self.results(('bukkie-create', 'rest_api', False), ('bukkie-create', 'rest_api', True))
        self.cli('apply')
        self.assertEqual(self.row('bukkie-create')['rest_api'], 'correct')

    def test_ungraded_and_manual_lessons_count_as_submitted(self):
        self.results(('StuartJSmith10-dev', 'manual', None))
        self.cli('apply')
        self.assertEqual(self.row('Stuart Smith')['manual'], 'submitted')

    def test_results_for_a_removed_lesson_are_ignored(self):
        self.results(('StuartJSmith10-dev', 'old_lesson', True))
        self.cli('apply')
        self.assertNotIn('old_lesson', self.roster().columns())

    def test_duplicate_login_warns_and_points_at_merge(self):
        self.cli('add', 'Copy', 'other')
        (self.dir / 'participants.csv').write_text(self.csv_text().replace(',other,', ',bukkie-create,'))
        self.results(('bukkie-create', 'fizzbuzz', True))
        _, out, _ = self.cli('apply')
        self.assertIn('on two rows', out)
        self.assertIn('merge', out)

    def test_new_lesson_column_is_added(self):
        (self.dir / 'lessons.json').write_text(json.dumps(LESSONS + [{'key': 'docker', 'label': 'Docker', 'repo': 'o/d', 'check': 'none'}]))
        self.cli('apply')
        self.assertIn('docker', self.roster().columns())


class EarlyBonusTests(Sandbox):
    """The first three pull requests on each exercise earn their authors +1 stretch each (pr_stretch)."""

    def bonus(self, who):
        return self.row(who).get('pr_stretch', '')

    def test_the_first_three_submissions_on_each_lesson_earn_one_each(self):
        self.results(('a1', 'fizzbuzz', None), ('a2', 'fizzbuzz', None), ('a3', 'fizzbuzz', None), ('a4', 'fizzbuzz', None),
                     ('a4', 'rest_api', None))
        self.cli('apply')
        self.assertEqual([self.bonus(x) for x in ('a1', 'a2', 'a3', 'a4')], ['1', '1', '1', '1'])  # a4: first on rest_api

    def test_two_of_the_first_three_by_one_person_earn_two(self):
        self.results(('a1', 'fizzbuzz', None), ('a1', 'fizzbuzz', None), ('a2', 'fizzbuzz', None))
        self.cli('apply')
        self.assertEqual((self.bonus('a1'), self.bonus('a2')), ('2', '1'))

    def test_order_is_when_they_were_opened_not_how_results_are_stored(self):
        self.results(('late', 'fizzbuzz', None), ('e1', 'fizzbuzz', None), ('e2', 'fizzbuzz', None), ('e3', 'fizzbuzz', None))
        data = json.loads((self.dir / 'grader' / 'results.json').read_text())
        data['submissions']['o/fizzbuzz#0']['created_at'] = '2026-12-01T00:00:00Z'
        (self.dir / 'grader' / 'results.json').write_text(json.dumps(data))
        self.cli('apply')
        self.assertEqual((self.bonus('late'), self.bonus('e1')), ('', '1'))  # none is left blank

    def test_recalculated_every_time_never_added_up(self):
        self.results(('a1', 'fizzbuzz', None))
        self.cli('apply')
        (self.dir / 'participants.csv').write_text(self.csv_text().replace('a1,a1,submitted,,,,,,1', 'a1,a1,submitted,,,,,,9'))
        self.cli('apply')
        self.cli('apply')
        self.assertEqual(self.bonus('a1'), '1')

    def test_counts_every_github_account_on_a_row_and_merge_recomputes_it(self):
        self.results(('bukkie-create', 'fizzbuzz', None), ('second', 'rest_api', None))
        self.cli('apply')
        self.cli('merge', 'bukkie-create', 'second')
        self.assertEqual(self.bonus('bukkie-create'), '2')

    @page.needs_node
    def test_counts_as_stretch_points(self):
        keys = [l['key'] for l in LESSONS]
        self.results(('a1', 'fizzbuzz', None))
        self.cli('apply')
        self.assertEqual(page.points(self.csv_text(), keys)['a1'], 10 + 5)

    def test_rows_without_a_github_account_are_left_alone(self):
        self.results(('a1', 'fizzbuzz', None))
        self.cli('apply')
        self.assertEqual(self.bonus('Bukky Adeyemi'), '')


class FileFormatTests(Sandbox):
    def test_an_old_github_column_is_read_and_saved_as_github_username(self):
        (self.dir / 'participants.csv').write_text(CSV.replace('github_username', 'github'))
        self.cli('award', 'StuartJSmith10-dev', 'helped')
        self.assertTrue(self.csv_text().startswith('name,github_username,'))
        self.assertEqual(self.row('StuartJSmith10-dev')['helped'], '1')

    def test_semicolon_and_bom_from_excel_survive_a_change(self):
        (self.dir / 'participants.csv').write_text('﻿' + CSV.replace(',', ';'), encoding='utf-8')
        self.cli('award', 'Stuart Smith', 'helped')
        text = (self.dir / 'participants.csv').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('﻿'))
        self.assertIn('Stuart Smith;StuartJSmith10-dev;correct', text)

    def test_names_with_commas_and_quotes_round_trip(self):
        self.cli('add', 'Rao, Asha "AR"')
        self.assertEqual(self.row('Rao, Asha "AR"')['name'], 'Rao, Asha "AR"')

    def test_saving_writes_one_spelling_for_each_value(self):
        (self.dir / 'participants.csv').write_text(
            'name,github_username,fizzbuzz,rest_api,manual,stretch,helped,bonus,pr_stretch\n'
            'Stuart Smith,StuartJSmith10-dev,Correct,In Review,none,0, 2 ,-1,0\n'
            'Bukky Adeyemi,,PASS,,,,,,\n')
        self.cli('award', 'Bukky Adeyemi', 'helped')
        self.assertEqual(self.csv_text().splitlines()[1:], ['Stuart Smith,StuartJSmith10-dev,correct,submitted,,,2,-1,',
                                                            'Bukky Adeyemi,,correct,,,,1,,'])

    @page.needs_node
    def test_the_real_file_keeps_its_scores_when_written_in_canonical_form(self):
        real = (GRADER.parent / 'participants.csv').read_text(encoding='utf-8')
        (self.dir / 'participants.csv').write_text(real, encoding='utf-8')
        (self.dir / 'lessons.json').write_text((GRADER.parent / 'lessons.json').read_text())
        keys = self.roster().lesson_keys()
        sheet = roster._Sheet(self.dir / 'participants.csv', keys)
        sheet.save()
        once = self.csv_text()
        self.assertEqual(page.read(once, keys), page.read(real, keys))
        roster._Sheet(self.dir / 'participants.csv', keys).save()
        self.assertEqual(self.csv_text(), once)

    def test_undo_matches_history_written_before_the_canonical_form(self):
        self.cli('award', 'Stuart Smith', 'stretch')
        history = json.loads((self.dir / 'grader' / 'history.json').read_text())
        for side in ('before', 'after'):
            history[-1]['changes'][0][side]['fizzbuzz'] = 'Correct'  # how older entries spelled it
        (self.dir / 'grader' / 'history.json').write_text(json.dumps(history))
        code, out, _ = self.cli('undo')
        self.assertNotIn('changed again', out)
        self.assertEqual(self.row('Stuart Smith')['stretch'], '1')

    def test_messy_whitespace_from_hand_edits_is_read(self):
        (self.dir / 'participants.csv').write_text('name,github,fizzbuzz\nStuart Smith,\tStuartJSmith10-dev ,\t correct\n')
        self.assertEqual(self.row('stuartjsmith10-dev')['fizzbuzz'], 'correct')


class WorkflowInputTests(Sandbox):
    """The facilitator workflows send form inputs as a JSON array (see .github/workflows/facilitator-*.yml)."""

    def test_json_args_with_shell_characters_are_plain_text(self):
        args = json.dumps(['rename', 'Stuart Smith', 'Stu "$(rm -rf /)" O\'Neil; `x`'])
        code, out, _ = self.cli('--args-json', args)
        self.assertEqual(code, 0)
        self.assertEqual(self.row('StuartJSmith10-dev')['name'], 'Stu "$(rm -rf /)" O\'Neil; `x`')

    def test_a_blank_optional_field_is_empty_not_the_word_none(self):
        # A form field left blank can arrive as JSON null; two people added without a login must not clash.
        for name in ('Ada Probe', 'Bob Probe'):
            code, out, _ = self.cli('--args-json', json.dumps(['add', name, None]))
            self.assertEqual(code, 0, out)
        self.assertEqual(self.row('Ada Probe')['github_username'], '')
        self.assertNotIn('None', self.csv_text())

    def test_applying_a_malformed_results_file_changes_nothing(self):
        (self.dir / 'grader' / 'results.json').write_text('{"submissions": {"o/r#1": {"task": "fizzbuzz", "login": "a b", "passed": true}}}')
        before = self.csv_text()
        code, _, err = self.cli('apply')
        self.assertEqual(code, 1)
        self.assertIn('Nothing was changed', err)
        self.assertEqual(self.csv_text(), before)

    def test_failure_is_shown_on_the_run_page(self):
        summary = self.dir / 'summary.md'
        self.patch(leaderboard.os, 'environ', {'GITHUB_STEP_SUMMARY': str(summary)})
        code, _, _ = self.cli('--args-json', json.dumps(['award', 'Nobody', 'helped', '1']))
        self.assertEqual(code, 1)
        self.assertIn('❌ Nothing was changed', summary.read_text())

    def test_every_facilitator_workflow_matches_a_command(self):
        workflows = GRADER.parent / '.github' / 'workflows'
        commands = set(leaderboard.parser()._subparsers._group_actions[0].choices)
        for wf in workflows.glob('facilitator-*.yml'):
            if wf.name == 'facilitator-action.yml':
                continue
            first = wf.read_text().split("args: '[\"", 1)[1].split('"', 1)[0]
            self.assertIn(first, commands, wf.name)


class OutcomeTests(Sandbox):
    """main() settles each facilitator change once: changed, refused (an answer, such as a misspelt name) or broken
    (a fault). The workflows, the practice copy and the tests read that, never the wording people see."""

    def outcome(self, *argv):
        path = self.dir / 'outcome'
        self.patch(leaderboard.os, 'environ', {'LEADERBOARD_OUTCOME': str(path)})
        code, _, _ = self.cli(*argv)
        return (code, *leaderboard.read_outcome(path))

    def test_a_change_made(self):
        self.assertEqual(self.outcome('award', 'Stuart Smith', 'helped'), (0, 'changed', ''))

    def test_a_refused_change_says_why_in_one_line(self):
        code, outcome, reason = self.outcome('award', 'Stuart Smit', 'helped')
        self.assertEqual((code, outcome), (1, 'refused'))
        self.assertTrue(reason.startswith('Nobody called "Stuart Smit"'), reason)
        self.assertNotIn('\n', reason)

    def test_a_batch_with_any_row_made_is_changed(self):
        rows = json.dumps([['award', 'Nobody Here', 'helped', '1'], ['award', 'Stuart Smith', 'helped', '1']])
        self.assertEqual(self.outcome('batch', 'oc1', rows)[:2], (0, 'changed'))

    def test_a_batch_with_every_row_refused_is_refused_and_still_saved(self):
        code, outcome, reason = self.outcome('batch', 'oc2', json.dumps([['award', 'Nobody Here', 'helped', '1']]))
        self.assertEqual((code, outcome), (0, 'refused'))  # exit 0: batches.json records why, for the page
        self.assertIn('0 of 1 changes made', reason)

    def test_a_batch_that_is_not_a_list_is_refused(self):
        self.assertEqual(self.outcome('batch', 'oc3', 'not json')[:2], (0, 'refused'))

    def test_a_fault_is_broken_and_still_raised(self):
        def explode(*a, **k):
            raise RuntimeError('disk full')
        self.patch(roster.Roster, 'award', explode)
        with self.assertRaises(RuntimeError):
            self.outcome('award', 'Stuart Smith', 'helped')
        self.assertEqual(leaderboard.read_outcome(self.dir / 'outcome')[0], 'broken')

    def test_arguments_the_workflow_should_never_send_are_broken(self):
        for argv in (('--args-json', 'not a JSON array'), ('award', 'Stuart Smith', 'gold')):
            (self.dir / 'outcome').write_text('changed\n')  # a stale file: broken must be written, not just missing
            with self.subTest(argv=argv), self.assertRaises((ValueError, SystemExit)):
                self.outcome(*argv)
            self.assertEqual(leaderboard.read_outcome(self.dir / 'outcome')[0], 'broken')

    def test_help_is_not_a_fault(self):
        with self.assertRaises(SystemExit) as raised:
            self.outcome('--help')
        self.assertEqual(raised.exception.code, 0)
        self.assertFalse((self.dir / 'outcome').exists())

    def test_a_listing_stays_off_the_run_page(self):
        summary = self.dir / 'summary.md'
        self.patch(leaderboard.os, 'environ', {'GITHUB_STEP_SUMMARY': str(summary)})
        self.assertEqual(self.cli('award', 'Stuart Smith', 'helped')[0], 0)
        written = summary.read_text()
        code, out, _ = self.cli('history', '3')
        self.assertEqual(code, 0)
        self.assertIn('Gave 1 help to Stuart Smith', out)
        self.assertEqual(summary.read_text(), written)

    def test_a_listing_has_no_outcome(self):
        self.patch(leaderboard.os, 'environ', {'LEADERBOARD_OUTCOME': str(self.dir / 'outcome')})
        self.cli('history')
        self.assertFalse((self.dir / 'outcome').exists())

    def test_a_whole_batch_refusal_keeps_its_cause_on_the_one_line(self):
        reason = self.outcome('batch', 'oc4', json.dumps([['grade']]))[2]
        self.assertIn('the whole batch oc4 was refused.', reason)
        self.assertIn('"grade" cannot go in a batch', reason)


class CommandLineTests(Sandbox):
    """leaderboard.py's own edges, from a terminal or a workflow."""

    def batch(self, batch_id, *rows):
        return self.cli('batch', batch_id, json.dumps([list(r) for r in rows]))

    def outcomes(self, batch_id):
        return json.loads((self.dir / 'grader' / 'batches.json').read_text())[batch_id]['rows']

    def test_the_run_page_shows_every_line_of_a_batch(self):
        summary = self.dir / 'summary.md'
        self.patch(leaderboard.os, 'environ', {'GITHUB_STEP_SUMMARY': str(summary)})
        self.batch('lines', ('award', 'Stuart Smith', 'helped', '1'), ('award', 'Bukky Adeyemi', 'stretch', '1'))
        text = summary.read_text()
        self.assertTrue(text.startswith('### ✅ 2 of 2 changes made (batch lines).\n\n✅ Gave 1 help to Stuart Smith'), text)
        self.assertIn('✅ Gave 1 stretch task to Bukky Adeyemi', text)

    def test_run_as_a_script_it_reads_its_arguments(self):
        r = subprocess.run([sys.executable, str(GRADER / 'leaderboard.py'), 'history', '1'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_no_command_is_an_error_not_an_apply(self):
        before = self.csv_text()
        with self.assertRaises(SystemExit) as e, contextlib.redirect_stderr(io.StringIO()):
            leaderboard.main([], root=self.dir)
        self.assertEqual(e.exception.code, 2)
        self.assertEqual(self.csv_text(), before)

    def test_the_repository_is_the_one_this_file_is_in(self):
        self.assertEqual(leaderboard.ROOT, GRADER.parent)

    def test_history_shows_the_last_ten_unless_asked(self):
        for n in range(12):
            self.cli('award', 'Stuart Smith', 'bonus', str(n + 1))
        self.assertEqual(len(self.cli('history')[1].strip().splitlines()), 10)
        self.assertEqual(len(self.cli('history', '3')[1].strip().splitlines()), 3)

    def test_a_row_asking_for_help_is_not_a_change(self):
        code, _, _ = self.batch('helprow', ('award', '-h'))
        self.assertEqual(code, 0)
        self.assertEqual(self.outcomes('helprow')[0]['message'], 'that is not a change')

    def test_rows_that_are_not_lists_refuse_the_whole_batch(self):
        code, _, err = self.cli('batch', 'notlists', json.dumps(['award', 'Stuart Smith']))
        self.assertEqual(code, 0)
        self.assertIn('not a JSON list of changes', err)
        self.assertEqual(self.csv_text(), CSV)


class BrokenLessonsTests(Sandbox):
    def test_a_broken_lessons_file_stops_actions_with_the_reason(self):
        (self.dir / 'lessons.json').write_text(json.dumps(LESSONS + [{'key': 'Bad Key', 'label': 'x', 'repo': 'o/r'}]))
        code, _, err = self.cli('award', 'Stuart Smith', 'helped')
        self.assertEqual(code, 1)
        self.assertIn('Nothing was changed', err)
        self.assertIn('must be lowercase', err)
        self.assertEqual(self.csv_text(), CSV)


class EdgeTests(Sandbox):
    """Cases mutation testing (grader/tests/mutate.py) showed no test covered."""

    def test_undo_merge_of_two_github_accounts_restores_both_rows(self):
        self.cli('add', 'Second Stuart', 'stuart-alt')
        before = self.csv_text()
        self.cli('merge', 'Stuart Smith', 'stuart-alt')
        self.assertEqual(self.row('stuart-alt')['github_username'], 'StuartJSmith10-dev stuart-alt')
        code, out, _ = self.cli('undo')
        self.assertEqual(code, 0)
        self.assertNotIn('Kept', out)  # the kept row is found again, though the re-added row shares its login
        self.assertEqual(self.csv_text(), before)

    def test_undo_does_not_depend_on_the_order_history_lists_changes(self):
        self.cli('add', 'Second Stuart', 'stuart-alt')
        before = self.csv_text()
        self.cli('merge', 'Stuart Smith', 'stuart-alt')
        history = json.loads((self.dir / 'grader' / 'history.json').read_text())
        history[-1]['changes'].reverse()  # the removed row listed before the edited one
        (self.dir / 'grader' / 'history.json').write_text(json.dumps(history))
        self.assertEqual(self.cli('undo')[0], 0)
        self.assertEqual(self.csv_text(), before)

    def test_merge_fills_an_empty_extra_column_from_the_duplicate_but_keeps_a_filled_one(self):
        (self.dir / 'participants.csv').write_text(CSV.replace('pr_stretch\n', 'pr_stretch,notes\n')
                                                   .replace('Bukky Adeyemi,,,,,2,1,,\n', 'Bukky Adeyemi,,,,,2,1,,,\n')
                                                   .replace('bukkie-create,bukkie-create,submitted,submitted,,,3,,\n',
                                                            'bukkie-create,bukkie-create,submitted,submitted,,,3,,,joined late\n'))
        self.cli('merge', 'Bukky Adeyemi', 'bukkie-create')
        self.assertEqual(self.row('Bukky Adeyemi')['notes'], 'joined late')
        self.cli('undo')
        (self.dir / 'participants.csv').write_text(self.csv_text().replace('Bukky Adeyemi,,,,,2,1,,,', 'Bukky Adeyemi,,,,,2,1,,,keep me'))
        self.cli('merge', 'Bukky Adeyemi', 'bukkie-create')
        self.assertEqual(self.row('Bukky Adeyemi')['notes'], 'keep me')

    def test_taking_away_everything_leaves_zero(self):
        self.assertEqual(self.cli('award', 'Stuart Smith', 'stretch', '-1')[0], 0)
        self.assertEqual(int(self.row('Stuart Smith')['stretch'] or 0), 0)

    def test_an_ambiguous_match_without_a_github_account_says_so(self):
        self.cli('add', 'Bukky Adeyemi Two')
        self.cli('rename', 'Bukky Adeyemi Two', 'Stuart Smith')
        code, _, err = self.cli('award', 'Stuart Smith', 'helped')
        self.assertEqual(code, 1)
        self.assertIn('Stuart Smith (@StuartJSmith10-dev), Stuart Smith (@no GitHub)', err)

    def test_a_local_change_is_signed_with_git_s_user_name_or_the_login(self):
        home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home)
        (home / 'gitconfig').write_text('[user]\n\tname = Pat Lead\n')
        env = {'GIT_CONFIG_GLOBAL': str(home / 'gitconfig'), 'GIT_CONFIG_NOSYSTEM': '1', 'USER': 'patl'}
        with mock.patch.dict('os.environ', env), mock.patch.dict('os.environ', {}, clear=False) as e:
            e.pop('GITHUB_ACTOR', None)
            self.assertEqual(roster.actor(), 'Pat Lead')
            (home / 'gitconfig').write_text('')
            self.assertEqual(roster.actor(), 'patl')


if __name__ == '__main__':
    unittest.main()
