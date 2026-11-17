"""Adding and removing a lesson from the facilitator page: `leaderboard.py add-lesson` and `remove-lesson`.

A lesson added this way is saved as "checking": nothing grades it and neither page shows it until a trial proves
its tests work (slice 2). Its tests are pinned from a public repository (its own, or another one and a folder in
it), as plain files only and within a size cap. Only the generic levels can be chosen, never a custom check.
The exercise repositories here are local git repositories standing in for GitHub.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

GRADER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRADER))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exercise_tests  # noqa: E402
import leaderboard  # noqa: E402
import lessons  # noqa: E402
from test_exercise_tests import git  # noqa: E402

LESSONS = [{'key': 'fizzbuzz', 'label': 'FizzBuzz', 'repo': 'o/fizzbuzz', 'check': 'none'}]
CSV = 'name,github_username,fizzbuzz,stretch,helped,bonus,pr_stretch\nAsha Rao,asha,submitted,,,,\n'
STARTER = {
    'build.gradle': "plugins { id 'java' }",
    'gradlew': '#!/bin/sh\n',
    'src/main/java/Greeting.java': 'class Greeting {}',
    'src/test/java/GreetingTest.java': 'class GreetingTest { /* v1 */ }',
}


class Sandbox(unittest.TestCase):
    """A leaderboard repository, and a place for stand-in exercise repositories (owner/name under self.github)."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.github = self.dir / 'github'
        (self.dir / 'grader').mkdir()
        (self.dir / 'lessons.json').write_text(json.dumps(LESSONS, indent=2) + '\n')
        (self.dir / 'participants.csv').write_text(CSV)
        real = exercise_tests.repo_url
        exercise_tests.repo_url = lambda repo: str(self.github / repo)
        self.addCleanup(setattr, exercise_tests, 'repo_url', real)

    def exercise(self, repo, files):
        path = self.github / repo
        path.mkdir(parents=True)
        git(path, 'init', '-q', '-b', 'main')
        git(path, 'config', 'user.email', 'author@example.com')
        git(path, 'config', 'user.name', 'Author')
        for rel, text in files.items():
            (path / rel).parent.mkdir(parents=True, exist_ok=True)
            (path / rel).write_text(text)
        git(path, 'add', '-A')
        git(path, 'commit', '-q', '-m', 'starter')
        return path

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = leaderboard.main(list(argv), root=self.dir)
        return code, out.getvalue(), err.getvalue()

    def entries(self):
        return {i['key']: i for i in json.loads((self.dir / 'lessons.json').read_text())}


class AddLessonTests(Sandbox):
    def test_a_lesson_with_its_own_tests_is_pinned_and_saved_as_checking(self):
        self.exercise('o/greeting', STARTER)
        code, out, err = self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'tests')
        self.assertEqual(code, 0, err)
        entry = self.entries()['greeting']
        self.assertEqual((entry['check'], entry['status']), ('tests', 'checking'))
        self.assertRegex(entry['tests_commit'], r'^[0-9a-f]{40}$')
        self.assertTrue((self.dir / 'grader/fixtures/greeting/src/test/java/GreetingTest.java').is_file())
        self.assertRegex(out, r'Added Greeting \(tests: 1 files from o/greeting at [0-9a-f]{7}\), checking until its trial passes')

    def test_a_checking_lesson_is_not_graded_or_shown(self):
        self.exercise('o/greeting', STARTER)
        self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'tests')
        self.assertEqual([lesson.key for lesson in lessons.load(self.dir)], ['fizzbuzz'])
        self.assertEqual([lesson.key for lesson in lessons.load(self.dir, checking=True)], ['fizzbuzz', 'greeting'])

    def test_tests_from_another_public_repository_and_folder(self):
        self.exercise('o/greeting', {k: v for k, v in STARTER.items() if 'src/test' not in k})  # the starter ships no tests
        self.exercise('o/solutions', {'greeting/' + k: v.replace('v1', 'solution') for k, v in STARTER.items()})
        code, _, err = self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'tests', 'o/solutions', 'greeting')
        self.assertEqual(code, 0, err)
        entry = self.entries()['greeting']
        self.assertEqual((entry['tests_repo'], entry['tests_dir']), ('o/solutions', 'greeting'))
        self.assertIn('solution', (self.dir / 'grader/fixtures/greeting/src/test/java/GreetingTest.java').read_text())

    def test_a_lesson_marked_by_hand_needs_no_tests(self):
        self.exercise('o/essay', {'README.md': 'Write about it.'})
        code, _, err = self.cli('add-lesson', 'essay', 'Essay', 'o/essay', 'none')
        self.assertEqual(code, 0, err)
        self.assertEqual(self.entries()['essay']['check'], 'none')
        self.assertFalse((self.dir / 'grader/fixtures/essay').exists())

    def test_build_needs_a_gradle_project(self):
        self.exercise('o/essay', {'README.md': 'Write about it.'})
        code, _, err = self.cli('add-lesson', 'essay', 'Essay', 'o/essay', 'build')
        self.assertEqual(code, 1)
        self.assertIn('no Gradle project', err)
        self.assertNotIn('essay', self.entries())

    def test_only_the_generic_levels_never_a_custom_check(self):
        self.exercise('o/greeting', STARTER)
        code, _, err = self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'container_image')
        self.assertEqual(code, 1)
        self.assertIn('none, build or tests', err)
        self.assertNotIn('greeting', self.entries())

    def test_a_key_or_repository_already_used_is_refused(self):
        self.exercise('o/greeting', STARTER)
        for argv, why in ((('fizzbuzz', 'FizzBuzz again', 'o/greeting', 'none'), 'already used'),
                          (('fizz2', 'FizzBuzz 2', 'o/fizzbuzz', 'none'), 'already the repository of FizzBuzz'),
                          (('Bad Key', 'Bad', 'o/greeting', 'none'), 'lowercase')):
            with self.subTest(argv=argv):
                code, _, err = self.cli('add-lesson', *argv)
                self.assertEqual(code, 1)
                self.assertIn(why, err)
        self.assertEqual(list(self.entries()), ['fizzbuzz'])

    def test_a_repository_that_cannot_be_fetched_changes_nothing(self):
        code, _, err = self.cli('add-lesson', 'ghost', 'Ghost', 'o/ghost', 'none')
        self.assertEqual(code, 1)
        self.assertIn('o/ghost', err)
        self.assertEqual(list(self.entries()), ['fizzbuzz'])

    def test_tests_with_a_symlink_are_refused(self):
        repo = self.exercise('o/greeting', STARTER)
        os.symlink('/etc/hosts', repo / 'src/test/java/hosts.txt')  # pinning runs where the deploy key is on disk
        git(repo, 'add', '-A')
        git(repo, 'commit', '-q', '-m', 'link')
        code, _, err = self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'tests')
        self.assertEqual(code, 1)
        self.assertIn('symbolic link', err)
        self.assertFalse((self.dir / 'grader/fixtures/greeting').exists())
        self.assertNotIn('greeting', self.entries())

    def test_a_tests_folder_that_is_a_link_out_of_the_repository_is_refused(self):
        outside = self.dir / 'outside'  # a project somewhere else on this machine, which must not be copied
        for rel, text in STARTER.items():
            (outside / rel).parent.mkdir(parents=True, exist_ok=True)
            (outside / rel).write_text(text.replace('v1', 'secret'))
        repo = self.exercise('o/solutions', {'README.md': 'solutions'})
        os.symlink(outside, repo / 'greeting')
        git(repo, 'add', '-A')
        git(repo, 'commit', '-q', '-m', 'link')
        self.exercise('o/greeting', STARTER)
        code, _, err = self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'tests', 'o/solutions', 'greeting')
        self.assertEqual(code, 1)
        self.assertIn('leads outside the repository', err)
        self.assertFalse((self.dir / 'grader/fixtures/greeting').exists())
        self.assertNotIn('greeting', self.entries())

    def test_tests_over_the_size_cap_are_refused(self):
        real = exercise_tests.MAX_BYTES
        exercise_tests.MAX_BYTES = 100  # the same rule as 5 MB, without a 5 MB file
        self.addCleanup(setattr, exercise_tests, 'MAX_BYTES', real)
        self.exercise('o/greeting', {**STARTER, 'src/test/resources/big.txt': 'x' * 200})
        code, _, err = self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'tests')
        self.assertEqual(code, 1)
        self.assertIn('MB under src/test/', err)

    def test_where_tests_come_from_only_applies_to_tests(self):
        self.exercise('o/greeting', STARTER)
        code, _, err = self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'none', 'o/solutions')
        self.assertEqual(code, 1)
        self.assertIn('only applies to a lesson checked with tests', err)

    def test_a_bad_key_is_refused_before_anything_is_fetched(self):
        code, _, err = self.cli('add-lesson', 'Bad Key', 'Bad', 'o/not-fetched', 'none')  # o/not-fetched does not exist
        self.assertEqual(code, 1)
        self.assertIn('lowercase', err)

    def test_too_many_test_files_are_refused(self):
        real = exercise_tests.MAX_FILES
        exercise_tests.MAX_FILES = 3  # the same rule as 500, without making 501 files
        self.addCleanup(setattr, exercise_tests, 'MAX_FILES', real)
        self.exercise('o/greeting', {**STARTER, **{f'src/test/resources/f{n}.txt': 'x' for n in range(3)}})
        code, _, err = self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'tests')
        self.assertEqual(code, 1)
        self.assertIn(f'more than {exercise_tests.MAX_FILES} files', err)

    def test_it_can_go_in_a_batch(self):
        self.exercise('o/greeting', STARTER)
        rows = json.dumps([['add-lesson', 'greeting', 'Greeting', 'o/greeting', 'tests'], ['award', 'Asha Rao', 'helped', '1']])
        code, out, err = self.cli('batch', 'b-lesson', rows)
        self.assertEqual(code, 0, err)
        self.assertIn('2 of 2 changes made', out)
        self.assertEqual(self.entries()['greeting']['status'], 'checking')


class RemoveLessonTests(Sandbox):
    def test_removes_the_lesson_and_its_tests(self):
        self.exercise('o/greeting', STARTER)
        self.cli('add-lesson', 'greeting', 'Greeting', 'o/greeting', 'tests')
        code, out, err = self.cli('remove-lesson', 'greeting')
        self.assertEqual(code, 0, err)
        self.assertNotIn('greeting', self.entries())
        self.assertFalse((self.dir / 'grader/fixtures/greeting').exists())
        self.assertIn('Removed Greeting', out)

    def test_removing_keeps_results_and_marks_so_adding_again_brings_them_back(self):
        results = {'people': {}, 'submissions': {'o/fizzbuzz#1': {'task': 'fizzbuzz', 'login': 'asha', 'passed': True,
                                                                  'url': 'u', 'created_at': '2026-11-01T00:00:00Z'}}}
        (self.dir / 'grader/results.json').write_text(json.dumps(results))
        self.exercise('o/fizzbuzz', {'README.md': 'FizzBuzz'})
        self.assertEqual(self.cli('remove-lesson', 'fizzbuzz')[0], 0)
        self.cli('award', 'Asha Rao', 'helped', '1')  # the sheet is written while the lesson is gone
        self.assertEqual(json.loads((self.dir / 'grader/results.json').read_text()), results)
        self.assertIn('fizzbuzz', (self.dir / 'participants.csv').read_text().splitlines()[0])
        self.assertEqual(self.cli('add-lesson', 'fizzbuzz', 'FizzBuzz', 'o/fizzbuzz', 'none')[0], 0)
        rows = (self.dir / 'participants.csv').read_text().splitlines()
        self.assertEqual(rows[1].split(',')[rows[0].split(',').index('fizzbuzz')], 'submitted', 'the mark came back with it')

    def test_adding_or_removing_a_lesson_forgets_its_old_trial(self):
        import submissions
        self.exercise('o/essay', {'README.md': 'Write about it.'})
        results = {'people': {}, 'submissions': {}, 'trials': {'essay': {'version': 'v', 'passed': False, 'reasons': ['old'], 'at': '2026-11-01T00:00:00Z'}}}
        (self.dir / 'grader/results.json').write_text(json.dumps(results))
        self.cli('add-lesson', 'essay', 'Essay', 'o/essay', 'none')
        self.assertIsNone(submissions.Submissions(self.dir).trial('essay'), 'added again: tried again')
        (self.dir / 'grader/results.json').write_text(json.dumps(results))
        self.cli('remove-lesson', 'essay')
        self.assertIsNone(submissions.Submissions(self.dir).trial('essay'))

    def test_a_custom_check_is_removed_through_a_pull_request(self):
        entries = LESSONS + [{'key': 'upgrade', 'label': 'Upgrade', 'repo': 'o/upgrade', 'check': 'framework_upgrade'}]
        (self.dir / 'lessons.json').write_text(json.dumps(entries, indent=2) + '\n')
        code, _, err = self.cli('remove-lesson', 'upgrade')
        self.assertEqual(code, 1)
        self.assertIn('through a pull request', err)
        self.assertIn('upgrade', self.entries())

    def test_an_unknown_lesson_is_refused(self):
        code, _, err = self.cli('remove-lesson', 'nope')
        self.assertEqual(code, 1)
        self.assertIn('No lesson "nope"', err)


if __name__ == '__main__':
    unittest.main()
