"""Submissions: what grader/results.json records about each pull request, and what that means for scores.

Run: python3 -m unittest discover grader/tests
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

GRADER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRADER))
from grade import PullRequest  # noqa: E402
from submissions import ResultsInvalid, Submissions  # noqa: E402


def lesson(key='alpha', automated=True, version='v1'):
    return SimpleNamespace(key=key, repo=f'o/{key}', check='c' if automated else 'none', version=version,
                           runner=(lambda ws, l: (True, [])) if automated else None)


def pr(number=1, login='ann', sha='s1', created_at='2026-11-01T09:00:00Z'):
    return PullRequest(number, login, sha, f'https://github.com/o/r/pull/{number}', created_at)


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        (self.dir / 'grader').mkdir()

    def subs(self):
        return Submissions(self.dir)

    def saved(self):
        return json.loads((self.dir / 'grader' / 'results.json').read_text())


class RecordingTests(Sandbox):
    def test_a_missing_file_is_empty_and_saving_creates_it(self):
        s = self.subs()
        self.assertEqual(s.best_statuses({'alpha'}), [])
        s.save()
        self.assertEqual(self.saved(), {'people': {}, 'submissions': {}})

    def test_a_graded_commit_does_not_need_grading_again(self):
        s, a = self.subs(), lesson()
        self.assertTrue(s.needs_grading(a, pr()))
        s.record_result(a, pr(), True, ['ok'])
        self.assertFalse(s.needs_grading(a, pr()))

    def test_a_new_commit_a_new_lesson_version_or_a_grader_error_needs_grading_again(self):
        s, a = self.subs(), lesson()
        s.record_result(a, pr(), True, ['ok'])
        self.assertTrue(s.needs_grading(a, pr(sha='s2')))
        self.assertTrue(s.needs_grading(lesson(version='v2'), pr()))
        s.record_result(a, pr(), None, ['grader error, will retry'])
        self.assertTrue(s.needs_grading(a, pr()))

    def test_a_hand_marked_lesson_never_needs_grading_and_is_recorded_as_submitted(self):
        s, manual = self.subs(), lesson(automated=False)
        self.assertFalse(s.needs_grading(manual, pr()))
        s.record(manual, pr())
        self.assertEqual(s.best_statuses({'alpha'}), [('ann', 'alpha', 'submitted')])
        self.assertIn('facilitator', self.saved_after(s)['submissions']['o/alpha#1']['reasons'][0])

    def test_recording_without_a_result_keeps_the_result_for_the_same_commit(self):
        s, a = self.subs(), lesson()
        s.record_result(a, pr(), True, ['ok'])
        s.record(lesson(version='v2'), pr())  # e.g. --no-run after the lesson changed
        self.assertEqual(s.best_statuses({'alpha'}), [('ann', 'alpha', 'correct')])
        s.record(a, pr(sha='s2'))  # a new commit: its result is not known yet
        self.assertEqual(s.best_statuses({'alpha'}), [('ann', 'alpha', 'submitted')])

    def test_a_still_valid_result_takes_the_pull_requests_latest_details(self):
        s, a = self.subs(), lesson()
        s.record_result(a, pr(), True, ['ok'])
        s.record(a, pr(login='Ann', created_at='2026-11-02T00:00:00Z'))
        entry = self.saved_after(s)['submissions']['o/alpha#1']
        self.assertEqual((entry['login'], entry['created_at'], entry['passed'], entry['version']), ('Ann', '2026-11-02T00:00:00Z', True, 'v1'))

    def test_saved_and_loaded_again(self):
        s = self.subs()
        s.record_result(lesson(), pr(), False, ['POST should return 201'])
        s.names['ann'] = 'Ann Lee'
        s.save()
        again = self.subs()
        self.assertEqual((again.name('ann'), again.name('bob')), ('Ann Lee', 'bob'))
        self.assertFalse(again.needs_grading(lesson(), pr()))

    def test_saving_keeps_anything_else_in_the_file(self):
        (self.dir / 'grader' / 'results.json').write_text(json.dumps({'note': 'kept', 'submissions': {}}))
        self.subs().save()
        self.assertEqual(self.saved()['note'], 'kept')

    def test_a_malformed_file_is_refused_with_every_problem(self):
        # The publish job trusts a file made in the job that ran pull-request code: check it before it is used.
        (self.dir / 'grader' / 'results.json').write_text(json.dumps({'people': {'ann': ['x']}, 'submissions': {
            'o/r#1': {'task': 'fizzbuzz', 'login': '=HYPERLINK("x")', 'passed': 'yes'}}}))
        with self.assertRaises(ResultsInvalid) as e:
            self.subs()
        for part in ('o/r#1: login', 'o/r#1: passed', 'people: ann'):
            self.assertIn(part, str(e.exception))

    def test_people_or_submissions_of_the_wrong_shape_is_refused(self):
        for data in ({'people': [], 'submissions': {}}, {'people': {}, 'submissions': []}):
            with self.subTest(data):
                (self.dir / 'grader' / 'results.json').write_text(json.dumps(data))
                with self.assertRaises(ResultsInvalid):
                    self.subs()

    def test_trials_of_the_wrong_shape_are_refused(self):
        # A trial in this file can put a lesson live, so it is checked like the rest before it is used.
        good = {'version': 'v1', 'passed': True, 'reasons': ['ok'], 'at': '2026-11-17T10:00:00Z'}
        for trials, why in (([], 'trials must be an object'), ({'g': {**good, 'passed': 'yes'}}, 'trials: g'),
                            ({'g': {k: v for k, v in good.items() if k != 'reasons'}}, 'trials: g'),
                            ({'g': {**good, 'reasons': 'ok'}}, 'trials: g'), ({'g': {**good, 'version': 1}}, 'trials: g'),
                            ({'g': {k: v for k, v in good.items() if k != 'at'}}, 'trials: g'), ({'g': 'passed'}, 'trials: g')):
            with self.subTest(trials=trials):
                (self.dir / 'grader' / 'results.json').write_text(json.dumps({'people': {}, 'submissions': {}, 'trials': trials}))
                with self.assertRaises(ResultsInvalid) as e:
                    self.subs()
                self.assertIn(why, str(e.exception))
        (self.dir / 'grader' / 'results.json').write_text(json.dumps({'people': {}, 'submissions': {}, 'trials': {'g': good}}))
        self.assertEqual(self.subs().trial('g'), good)

    def test_saved_with_sorted_keys_so_a_change_is_a_small_diff(self):
        (self.dir / 'grader' / 'results.json').write_text(json.dumps({'submissions': {}, 'people': {'zed': 'Z', 'amy': 'A'}}))
        self.subs().save()
        text = (self.dir / 'grader' / 'results.json').read_text()
        self.assertLess(text.index('"amy"'), text.index('"zed"'))
        self.assertLess(text.index('"people"'), text.index('"submissions"'))

    def saved_after(self, s):
        s.save()
        return self.saved()


class StatusTests(Sandbox):
    def test_correct_beats_submitted_across_a_persons_pull_requests(self):
        s = self.subs()
        s.record_result(lesson(), pr(1), False, ['no'])
        s.record_result(lesson(), pr(2), True, ['ok'])
        self.assertEqual(s.best_statuses({'alpha'}), [('ann', 'alpha', 'correct')])

    def test_logins_differing_only_in_case_are_one_person(self):
        s = self.subs()
        s.record_result(lesson(), pr(1, login='ann'), True, ['ok'])
        s.record_result(lesson(), pr(2, login='ANN'), False, ['no'])
        self.assertEqual(len(s.best_statuses({'alpha'})), 1)

    def test_lessons_not_asked_for_are_left_out(self):
        s = self.subs()
        s.record_result(lesson('old'), pr(), True, ['ok'])
        self.assertEqual(s.best_statuses({'alpha'}), [])


class EarlyBonusTests(Sandbox):
    def test_the_first_three_opened_on_each_lesson_earn_one_each(self):
        s = self.subs()
        for n, who in enumerate(['late', 'e1', 'e2', 'e3'], 1):
            s.record(lesson(), pr(n, who, created_at=f'2026-11-01T00:00:0{n}Z'))
        s.record(lesson(), pr(1, 'late', created_at='2026-12-01T00:00:00Z'))  # reopened details: actually opened last
        s.record(lesson('beta'), pr(9, 'late'))
        self.assertEqual(s.early_bonus({'alpha', 'beta'}), {'e1': 1, 'e2': 1, 'e3': 1, 'late': 1})

    def test_results_without_an_opened_time_are_ordered_by_pull_request_number(self):
        (self.dir / 'grader' / 'results.json').write_text(json.dumps({'people': {}, 'submissions': {
            f'o/f#{n}': {'login': f'p{n}', 'task': 'alpha', 'passed': None, 'url': f'https://github.com/o/f/pull/{n}'}
            for n in (10, 2, 3, 1)}}))
        self.assertEqual(self.subs().early_bonus({'alpha'}), {'p1': 1, 'p2': 1, 'p3': 1})

    def test_one_person_can_earn_more_than_one(self):
        s = self.subs()
        s.record(lesson(), pr(1, 'Ann'))
        s.record(lesson(), pr(2, 'ann', created_at='2026-11-01T09:00:01Z'))
        self.assertEqual(s.early_bonus({'alpha'}), {'ann': 2})


class StatsTests(Sandbox):
    def test_counts_per_lesson(self):
        s = self.subs()
        s.record_result(lesson(), pr(1, 'x'), True, ['ok'])
        s.record_result(lesson(), pr(2, 'x'), False, ['no'])
        s.record_result(lesson(), pr(3, 'y'), None, ['grader error'])
        s.record_result(lesson('beta'), pr(4, 'z'), True, ['ok'])
        self.assertEqual(s.stats('alpha'), {'submissions': 3, 'people': 2, 'correct': 1})
        self.assertEqual(s.stats('gamma'), {'submissions': 0, 'people': 0, 'correct': 0})


if __name__ == '__main__':
    unittest.main()
