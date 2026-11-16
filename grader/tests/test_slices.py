"""Slices: one feature at a time, from where it starts to the points the page shows.

Each test goes the whole way through the real code and files (no step replaced) except at the edges: GitHub is
the in-memory FakeGitHub, checks are stand-ins, and points are read by the page's own scoring.js in Node. Where
the unit tests check each module, these check that the modules agree with each other.
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
sys.path.insert(0, str(TESTS))
import checks  # noqa: E402
import grade  # noqa: E402
import leaderboard  # noqa: E402
import page  # noqa: E402
from test_grading import STAND_INS, FakeGitHub  # noqa: E402

LESSONS = [{'key': 'alpha', 'label': 'Alpha', 'repo': 'o/alpha', 'check': 'stand_in_pass'},
           {'key': 'beta', 'label': 'Beta', 'repo': 'o/beta', 'check': 'stand_in_fail'},
           {'key': 'manual', 'label': 'Manual', 'repo': 'o/manual', 'check': 'none'}]
KEYS = [l['key'] for l in LESSONS]
CSV = 'name,github_username,alpha,beta,manual,stretch,helped,bonus,pr_stretch\nAnn Lee,ann,,,,,,,\n'


@page.needs_node
class Slice(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        (self.dir / 'grader' / 'fixtures').mkdir(parents=True)
        (self.dir / 'lessons.json').write_text(json.dumps(LESSONS))
        (self.dir / 'participants.csv').write_text(CSV)
        self.github = FakeGitHub()
        patcher = mock.patch.dict(checks.CHECKS, STAND_INS)
        patcher.start()
        self.addCleanup(patcher.stop)

    def form(self, *args):
        """A facilitator form, exactly as facilitator-action.yml passes it: one JSON array."""
        return self.run_cli('--args-json', json.dumps(list(args)))

    def grading_run(self):
        """grade.yml: the grade job grades into its own checkout; the publish job applies that file to main's."""
        job = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, job)
        shutil.copytree(self.dir, job, dirs_exist_ok=True)
        grade.grade_all(job, source=self.github, log=lambda *_: None)
        code, _ = self.run_cli('apply', str(job / 'grader' / 'results.json'))
        self.assertEqual(code, 0)

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            return leaderboard.main(list(argv), root=self.dir), out.getvalue()

    def points(self):
        return page.points((self.dir / 'participants.csv').read_text(), KEYS)


class FacilitatorSlices(Slice):
    def test_award_reaches_the_page_as_points(self):
        self.assertEqual(self.form('award', 'Ann Lee', 'helped', '3'), (0, 'Gave 3 helps to Ann Lee (helped: 0 -> 3)\n'))
        self.assertEqual(self.points(), {'Ann Lee': 3 * 5})

    def test_mark_then_undo_on_the_page(self):
        self.form('mark', 'ann', 'manual', 'correct')
        self.assertEqual(self.points(), {'Ann Lee': 30})
        self.form('undo')
        self.assertEqual(self.points(), {'Ann Lee': 0})

    def test_a_blank_optional_field_is_empty_not_the_word_none(self):
        # GitHub passes a blank optional input as null inside the JSON array.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            leaderboard.main(['--args-json', '["add", "Bo Day", null]'], root=self.dir)
        self.assertEqual(page.read((self.dir / 'participants.csv').read_text(), KEYS)['rows'][-1]['name'], 'Bo Day')
        self.assertNotIn('None', (self.dir / 'participants.csv').read_text())


class GradingSlices(Slice):
    def test_a_passing_pull_request_reaches_the_page(self):
        self.github.add('o/alpha', 1, 'ann', 'a1')
        self.grading_run()
        self.assertEqual(self.points(), {'Ann Lee': 30 + 5})  # correct, and the first pull request on alpha

    def test_a_failing_one_counts_as_submitted_and_a_new_person_is_added(self):
        self.github.add('o/beta', 1, 'bob', 'b1')
        self.github.names['bob'] = 'Bob Ray'
        self.grading_run()
        self.assertEqual(self.points(), {'Ann Lee': 0, 'Bob Ray': 10 + 5})

    def test_a_withdrawn_pull_request_gives_up_its_bonus_but_not_its_status(self):
        for n, login in enumerate(['ann', 'bob', 'cy', 'dee'], 1):
            self.github.add('o/alpha', n, login, f's{n}', created_at=f'2026-11-01T09:00:0{n}Z')
        self.grading_run()
        self.assertEqual(self.points()['dee'], 30)
        self.github.prs['o/alpha'] = [p for p in self.github.prs['o/alpha'] if p.login != 'ann']
        self.grading_run()
        points = self.points()
        self.assertEqual((points['Ann Lee'], points['dee']), (30, 30 + 5))

    def test_a_facilitator_change_made_during_grading_survives_publishing(self):
        self.github.add('o/alpha', 1, 'ann', 'a1')
        job = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, job)
        shutil.copytree(self.dir, job, dirs_exist_ok=True)  # the grade job checked out main here
        grade.grade_all(job, source=self.github, log=lambda *_: None)
        self.form('award', 'Ann Lee', 'bonus', '7')  # meanwhile, on main
        self.run_cli('apply', str(job / 'grader' / 'results.json'))
        self.assertEqual(self.points(), {'Ann Lee': 30 + 5 + 7})


if __name__ == '__main__':
    unittest.main()
