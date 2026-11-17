"""The Lesson module: lessons.json loaded, validated, and resolved to checks, test files and versions.

Run: python3 -m unittest discover grader/tests
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

GRADER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRADER))
import lessons  # noqa: E402

VALID = [
    {'key': 'fizzbuzz', 'label': 'FizzBuzz', 'repo': 'o/fizz', 'check': 'fizzbuzz'},
    {'key': 'manual', 'label': 'Manual', 'repo': 'o/manual', 'check': 'none'},
    {'key': 'upgrade', 'label': 'Upgrade', 'repo': 'o/up', 'check': 'tests'},
]


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.file = self.dir / 'lessons.json'
        self.fixtures = self.dir / 'grader' / 'fixtures'
        self.write(VALID)

    def write(self, items):
        self.file.write_text(json.dumps(items))

    def load(self):
        return lessons.load(self.dir)


class LoadingTests(Sandbox):
    def test_valid_lessons_load_in_order(self):
        self.assertEqual([l.key for l in self.load()], ['fizzbuzz', 'manual', 'upgrade'])
        self.assertEqual(self.load()[0].label, 'FizzBuzz')
        self.assertEqual(self.load()[0].repo, 'o/fizz')

    def test_where_tests_come_from_must_be_a_repository_and_a_folder_in_it(self):
        base = {'key': 'g', 'label': 'G', 'repo': 'o/g', 'check': 'none', 'status': 'checking'}
        for field, value, why in (('tests_repo', 'not a repo', 'tests_repo must look like owner/name'),
                                  ('tests_repo', '../o/x', 'tests_repo must look like owner/name'),
                                  ('tests_dir', '../outside', 'tests_dir must be a folder'),
                                  ('tests_dir', '/abs', 'tests_dir must be a folder'),
                                  ('tests_dir', '.git', 'tests_dir must be a folder'),
                                  ('status', 'live', 'status can only be "checking"')):
            with self.subTest(field=field, value=value):
                self.write([{**base, field: value}])
                with self.assertRaises(lessons.LessonsInvalid) as e:
                    self.load()
                self.assertIn(why, str(e.exception))
        self.write([{**base, 'tests_repo': 'o/solutions', 'tests_dir': 'app/greeting'}])
        self.assertEqual(self.load(), [], 'a checking lesson is left out unless asked for')
        (only,) = lessons.load(self.dir, checking=True)
        self.assertEqual((only.tests_repo, only.tests_dir, only.status), ('o/solutions', 'app/greeting', 'checking'))

    def test_every_problem_is_reported_at_once(self):
        self.write([{'key': 'Bad Key', 'label': 'x', 'repo': 'o/r', 'check': 'none'},
                    {'key': 'helped', 'label': 'x', 'repo': 'o/r', 'check': 'none'},
                    {'key': 'ok', 'label': '', 'repo': 'not-a-repo', 'check': 'magic'},
                    {'key': 'ok', 'label': 'Again', 'repo': 'o/r'}])
        with self.assertRaises(lessons.LessonsInvalid) as e:
            self.load()
        msg = str(e.exception)
        for part in ('lowercase', '"helped" is already used', 'owner/name', 'check must be one of', 'needs a label', '"ok" is already used',
                     'o/r is already the repository of x: one lesson per repository'):
            self.assertIn(part, msg)
        self.assertEqual(len(e.exception.problems), 8)  # o/r is used three times: two of them are a second lesson on it

    def test_a_key_cannot_be_a_column_the_sheet_already_uses(self):
        for column in ('name', 'github_username', 'stretch', 'helped', 'bonus', 'pr_stretch'):
            self.write([{'key': column, 'label': 'x', 'repo': 'o/r', 'check': 'none'}])
            with self.assertRaisesRegex(lessons.LessonsInvalid, f'"{column}" is already used'):
                self.load()

    def test_a_misspelt_field_is_reported_not_ignored(self):
        # Ignoring "chek" would quietly turn an automated lesson into a hand-marked one.
        self.write([{'key': 'a', 'label': 'A', 'repo': 'o/a', 'chek': 'tests'}])
        with self.assertRaisesRegex(lessons.LessonsInvalid, 'unknown field "chek"'):
            self.load()

    def test_a_field_that_is_not_text_is_reported(self):
        self.write([{'key': 7, 'label': ['A'], 'repo': 'o/a', 'check': None}])
        with self.assertRaises(lessons.LessonsInvalid) as e:
            self.load()
        self.assertEqual(sum('must be text' in p for p in e.exception.problems), 3)

    def test_a_key_cannot_be_a_column_the_board_already_has(self):
        for key in ('pr_stretch', 'github', 'restapi', 'stretch'):
            with self.subTest(key):
                self.write([{'key': key, 'label': 'X', 'repo': 'o/r', 'check': 'none'}])
                with self.assertRaises(lessons.LessonsInvalid) as e:
                    self.load()
                self.assertIn(f'"{key}" is already used', str(e.exception))

    def test_problems_name_the_lesson_by_its_place_and_key(self):
        self.write([{'key': 'ok', 'label': 'Ok', 'repo': 'o/r'}, {'key': 5, 'label': 'X', 'repo': 'o/r'}, 'not a lesson'])
        with self.assertRaises(lessons.LessonsInvalid) as e:
            self.load()
        self.assertIn('it must be a list of lessons', str(e.exception))
        self.write([{'key': 'ok', 'label': '', 'repo': 'o/r'}, {'key': 5, 'label': 'X', 'repo': 'o/r'}])
        with self.assertRaises(lessons.LessonsInvalid) as e:
            self.load()
        self.assertIn('lesson 1 (ok): needs a label', e.exception.problems)
        self.assertIn('lesson 2: key must be text', e.exception.problems)

    def test_pinning_keeps_lessons_json_as_written(self):
        self.write([{'key': 'cafe', 'label': 'Café', 'repo': 'o/r', 'check': 'none'}])
        lessons.record_pinned(self.dir, 'cafe', 'a' * 40)
        text = self.file.read_text(encoding='utf-8')
        self.assertIn('"label": "Café"', text)
        self.assertIn('\n  {\n    "key": "cafe"', text)

    def test_missing_check_means_none(self):
        self.write([{'key': 'a', 'label': 'A', 'repo': 'o/a'}])
        self.assertEqual(self.load()[0].check, 'none')

    def test_tests_commit_is_a_full_commit_id_on_a_tests_lesson(self):
        sha = 'a' * 40
        self.write([{'key': 'a', 'label': 'A', 'repo': 'o/a', 'check': 'tests', 'tests_commit': sha}])
        self.assertEqual(self.load()[0].check, 'tests')
        for item in ({'check': 'tests', 'tests_commit': 'main'}, {'check': 'build', 'tests_commit': sha}):
            self.write([{'key': 'a', 'label': 'A', 'repo': 'o/a', **item}])
            with self.assertRaisesRegex(lessons.LessonsInvalid, 'tests_commit'):
                self.load()

    def test_not_a_list_or_not_json(self):
        for text in ('{not json', '{"key": "a"}'):
            self.file.write_text(text)
            with self.assertRaises(lessons.LessonsInvalid):
                self.load()

    def test_the_real_lessons_file_is_valid(self):
        self.assertTrue(lessons.load())


class CheckTests(Sandbox):
    def test_runner_is_the_named_check_or_none(self):
        import checks
        by_key = {l.key: l for l in self.load()}
        self.assertIs(by_key['fizzbuzz'].runner, checks.CHECKS['fizzbuzz'])
        self.assertIsNone(by_key['manual'].runner)

    def test_each_check_is_a_module_named_after_it(self):
        import checks
        modules = {f.stem for f in (lessons.HERE / 'checks').glob('*.py')} - {'__init__', *checks.SHARED}
        self.assertEqual(set(checks.names()), modules)
        for name in checks.names():
            self.assertEqual(checks.runner(name).__module__, f'checks.{name}')

    def test_a_check_imports_only_the_shared_modules_so_its_version_covers_its_code(self):
        import re
        import checks
        self.assertTrue(checks.names())
        for name in checks.names():
            source = (lessons.HERE / 'checks' / f'{name}.py').read_text()
            used = set(re.findall(r'^from \.(\w+) import|^from checks\.(\w+) import', source, re.M))
            others = {m for pair in used for m in pair if m} - set(checks.SHARED)
            self.assertEqual(others, set(), f'checks/{name}.py imports another check')

    def test_test_files_live_in_the_lessons_fixture_folder(self):
        self.assertEqual(self.load()[2].test_files, self.fixtures / 'upgrade')


class VersionTests(Sandbox):
    """A lesson's version changes when anything deciding its result changes, and only then."""

    def versions(self):
        return {l.key: l.version for l in self.load()}

    def test_stable_when_nothing_changes(self):
        self.assertEqual(self.versions(), self.versions())

    def test_changing_one_lessons_test_files_regrades_only_that_lesson(self):
        before = self.versions()
        (self.fixtures / 'upgrade').mkdir(parents=True)
        (self.fixtures / 'upgrade' / 'ApiTest.java').write_text('class ApiTest {}')
        after = self.versions()
        self.assertNotEqual(before['upgrade'], after['upgrade'])
        self.assertEqual((before['fizzbuzz'], before['manual']), (after['fizzbuzz'], after['manual']))

    def test_changing_one_lessons_check_regrades_only_that_lesson(self):
        before = self.versions()
        self.write([VALID[0], {**VALID[1], 'check': 'build'}, VALID[2]])
        after = self.versions()
        self.assertNotEqual(before['manual'], after['manual'])
        self.assertEqual((before['fizzbuzz'], before['upgrade']), (after['fizzbuzz'], after['upgrade']))

    def test_editing_a_check_module_regrades_only_its_lessons(self):
        import importlib
        import checks
        source = 'LIMIT = 1\n\n\ndef check(ws, lesson):\n    return LIMIT == 1, ["ok"]\n'
        sys.path.insert(0, str(self.dir))
        self.addCleanup(sys.path.remove, str(self.dir))

        def versions(a_text, b_text):
            stand_ins = {}
            for name, text in (('stand_in_a', a_text), ('stand_in_b', b_text)):
                (self.dir / f'{name}.py').write_text(text)
                sys.modules.pop(name, None)
                stand_ins[name] = importlib.import_module(name).check
            with mock.patch.dict(checks.CHECKS, {'check_a': stand_ins['stand_in_a'], 'check_b': stand_ins['stand_in_b']}):
                self.write([{'key': 'a', 'label': 'A', 'repo': 'o/a', 'check': 'check_a'},
                            {'key': 'b', 'label': 'B', 'repo': 'o/b', 'check': 'check_b'}])
                return {l.key: l.version for l in self.load()}

        before = versions(source, source)
        after = versions(source.replace('LIMIT = 1', 'LIMIT = 2'), source)  # a constant, not just the function
        self.assertNotEqual(before['a'], after['a'])
        self.assertEqual(before['b'], after['b'])

    def test_the_toolkit_and_the_executor_are_shared_by_every_check(self):
        self.assertIn(lessons.HERE / 'executor.py', lessons.SHARED_CODE)
        self.assertIn(lessons.HERE / 'checks' / 'toolkit.py', lessons.SHARED_CODE)
        self.assertTrue(all(p.exists() for p in lessons.SHARED_CODE))

    def test_the_code_that_runs_participant_code_is_part_of_every_version(self):
        with mock.patch.object(lessons, 'SHARED_CODE', [self.dir / 'executor_stand_in.py']):
            (self.dir / 'executor_stand_in.py').write_text('x = 1')
            before = {l.key: l.version for l in self.load() if l.runner}
            (self.dir / 'executor_stand_in.py').write_text('x = 2')
            after = {l.key: l.version for l in self.load() if l.runner}
        self.assertTrue(all(before[k] != after[k] for k in before))

    def test_label_does_not_affect_the_version(self):
        before = self.versions()
        self.write([{**VALID[0], 'label': 'Fizz Buzz!'}, VALID[1], VALID[2]])
        self.assertEqual(before['fizzbuzz'], self.versions()['fizzbuzz'])



class CatalogueTests(unittest.TestCase):
    """Lessons are a catalogue (keys, labels, repositories) that facilitator actions read; only grading loads a
    lesson's check. So a broken check module cannot stop a facilitator, or grading of the other lessons."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        shutil.copytree(GRADER, self.root / 'grader', ignore=shutil.ignore_patterns('tests', 'fixtures', '__pycache__', '*.json'))
        shutil.copy(GRADER.parent / 'scoring.js', self.root)
        shutil.copy(GRADER.parent / 'lessons.json', self.root)
        keys = [l['key'] for l in json.loads((self.root / 'lessons.json').read_text())]
        (self.root / 'participants.csv').write_text('name,github_username,' + ','.join(keys) + '\nAnn,ann' + ',' * len(keys) + '\n')

    def run_py(self, code):
        r = subprocess.run([sys.executable, '-c', code], cwd=self.root / 'grader', capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_facilitator_actions_load_no_check(self):
        out = self.run_py('import sys, leaderboard\n'
                          'assert leaderboard.main(["award", "Ann", "helped"]) == 0\n'
                          'assert leaderboard.main(["undo"]) == 0\n'
                          'print(sorted(m for m in sys.modules if m.startswith("checks.") or m == "executor"))')
        self.assertEqual(out.splitlines()[-1], '[]')

    def test_a_broken_check_does_not_stop_facilitators(self):
        (self.root / 'grader' / 'checks' / 'container_image.py').write_text('def check(ws, lesson:\n')
        out = self.run_py('import leaderboard\nprint(leaderboard.main(["award", "Ann", "helped"]))')
        self.assertEqual(out.splitlines()[-1], '0')
        self.assertIn('Ann,ann', (self.root / 'participants.csv').read_text())

    def test_a_broken_check_skips_only_its_own_lessons_when_grading(self):
        checks_dir = self.root / 'grader' / 'checks'
        (checks_dir / 'stand_in_pass.py').write_text('def check(ws, lesson):\n    return True, ["fine"]\n')
        (checks_dir / 'broken.py').write_text('def check(ws, lesson:\n')
        (self.root / 'lessons.json').write_text(json.dumps([
            {'key': 'alpha', 'label': 'Alpha', 'repo': 'o/alpha', 'check': 'stand_in_pass'},
            {'key': 'beta', 'label': 'Beta', 'repo': 'o/beta', 'check': 'broken'}]))
        out = self.run_py(
            'import json, grade\n'
            'class Source:\n'
            '    def pull_requests(self, repo): return [grade.PullRequest(1, "ann", "s1", f"https://github.com/{repo}/pull/1")]\n'
            '    def display_name(self, login): return "Ann"\n'
            '    def checkout(self, repo, number, dest): pass\n'
            'log = []\n'
            'subs = grade.grade_all("..", source=Source(), log=log.append)\n'
            'saved = json.load(open("results.json"))["submissions"]\n'
            'print(json.dumps({"log": log, "passed": {k: v.get("passed") for k, v in saved.items()}}))')
        result = json.loads(out.splitlines()[-1])
        self.assertEqual(result['passed'].get('o/alpha#1'), True)  # the other lesson is still graded
        self.assertNotIn('o/beta#1', result['passed'])           # skipped this run, like an unreachable repository
        self.assertTrue(any('beta' in line and 'cannot load its check' in line for line in result['log']), result['log'])

    def test_an_unknown_check_is_refused_without_loading_any(self):
        (self.root / 'lessons.json').write_text(json.dumps([{'key': 'alpha', 'label': 'Alpha', 'repo': 'o/a', 'check': 'nope'}]))
        out = self.run_py('import sys, lessons\n'
                          'try:\n    lessons.load("..")\nexcept lessons.LessonsInvalid as e:\n    print(e.problems[0])\n'
                          'print(sorted(m for m in sys.modules if m.startswith("checks.")))')
        problem, loaded = out.splitlines()[-2:]
        names = sorted(f.stem for f in (self.root / 'grader' / 'checks').glob('*.py') if f.stem not in ('__init__', 'toolkit'))
        self.assertIn('check must be one of none, ' + ', '.join(names), problem)
        self.assertEqual(loaded, '[]')


if __name__ == '__main__':
    unittest.main()
