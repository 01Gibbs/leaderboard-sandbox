"""A lesson's life, through its one module (grader/lesson_lifecycle.py): saved as checking, tried by grading
(once per version, again when the grader could not finish, a day after a failure), put live when its trial passed
for the lesson as it is now. Running a trial is a seam: these tests stand in for it."""
import dataclasses
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lesson_lifecycle  # noqa: E402
import lessons  # noqa: E402
from submissions import Submissions  # noqa: E402

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / 'grader' / 'fixtures').mkdir(parents=True)
        self.write([{'key': 'alpha', 'label': 'Alpha', 'repo': 'o/alpha', 'check': 'build'},
                    {'key': 'gamma', 'label': 'Gamma', 'repo': 'o/gamma', 'check': 'build', 'status': 'checking',
                     'added': '2026-11-18T09:00:00.000000Z'}])
        self.tried = []

    def write(self, entries):
        (self.root / 'lessons.json').write_text(json.dumps(entries))

    def entries(self):
        return {e['key']: e for e in json.loads((self.root / 'lessons.json').read_text())}

    def try_due(self, verdict, now=NOW):
        def run_trial(lesson):
            self.tried.append(lesson.key)
            return verdict
        subs = Submissions(self.root)
        lesson_lifecycle.try_due(self.root, subs, run_trial, now=now, log=lambda line: None)
        subs.save()

    def promote(self):
        subs = Submissions(self.root)
        lines = lesson_lifecycle.promote_passed(self.root, subs)
        return lines

    def test_only_a_lesson_being_checked_is_tried(self):
        self.try_due((True, ['the starter builds']))
        self.assertEqual(self.tried, ['gamma'])

    def test_a_passed_trial_puts_it_live_and_says_why(self):
        self.try_due((True, ['the starter builds']))
        self.assertEqual(self.promote(), ['Gamma is live: the starter builds'])
        self.assertNotIn('status', self.entries()['gamma'])
        self.assertEqual(self.promote(), [], 'once live, there is nothing more to put live')

    def test_a_failed_trial_keeps_it_checking_and_is_tried_again_a_day_later(self):
        self.try_due((False, ['the starter does not build']))
        self.assertEqual(self.promote(), [])
        self.assertEqual(self.entries()['gamma']['status'], 'checking')
        self.try_due((True, ['the starter builds']), now=NOW + timedelta(hours=23))
        self.assertEqual(self.tried, ['gamma'], 'not straight away')
        self.try_due((True, ['the starter builds']), now=NOW + timedelta(hours=25))
        self.assertEqual(self.tried, ['gamma', 'gamma'])

    def test_a_trial_the_grader_could_not_finish_is_tried_again_next_run(self):
        self.try_due((None, ['grader error, will try again']))
        self.try_due((True, ['the starter builds']))
        self.assertEqual(self.tried, ['gamma', 'gamma'])
        self.assertEqual(self.promote(), ['Gamma is live: the starter builds'])

    def test_a_passed_trial_is_not_run_again(self):
        self.try_due((True, ['the starter builds']))
        self.try_due((True, ['the starter builds']), now=NOW + timedelta(days=3))
        self.assertEqual(self.tried, ['gamma'])

    def test_a_trial_of_the_lesson_as_it_was_does_not_put_it_live(self):
        self.try_due((True, ['the starter builds']))
        for change in ({'repo': 'o/gamma-moved'}, {'added': '2026-11-18T10:00:00.000000Z'}):  # moved; added again
            with self.subTest(change=change):
                entries = list(self.entries().values())
                entries[-1].update(change)
                self.write(entries)
                self.assertEqual(self.promote(), [])
                self.try_due((True, ['the starter builds']))
                self.assertEqual(self.tried[-1], 'gamma', 'the lesson as it is now is tried')
                self.write([e if e['key'] != 'gamma' else {**e, 'status': 'checking'} for e in self.entries().values()])

    def test_new_pinned_tests_are_a_new_version(self):
        self.try_due((True, ['the starter builds']))
        (self.root / 'grader' / 'fixtures' / 'gamma').mkdir()
        (self.root / 'grader' / 'fixtures' / 'gamma' / 'GammaTest.java').write_text('class GammaTest {}')
        self.assertEqual(self.promote(), [])
        self.try_due((True, ['the starter builds']))
        self.assertEqual(self.tried, ['gamma', 'gamma'])

    def test_a_lesson_put_live_by_hand_is_left_alone(self):
        self.write([e if e['key'] != 'gamma' else {k: v for k, v in e.items() if k != 'status'} for e in self.entries().values()])
        self.try_due((False, ['never asked']))
        self.assertEqual((self.tried, self.promote()), ([], []))

    def test_the_version_is_what_the_trial_depends_on(self):
        gamma = next(lesson for lesson in lessons.load(self.root, checking=True) if lesson.key == 'gamma')
        self.assertEqual(lesson_lifecycle.version(gamma), lesson_lifecycle.version(gamma))
        moved = dataclasses.replace(gamma, repo='o/elsewhere')
        self.assertNotEqual(lesson_lifecycle.version(gamma), lesson_lifecycle.version(moved))


if __name__ == '__main__':
    unittest.main()
