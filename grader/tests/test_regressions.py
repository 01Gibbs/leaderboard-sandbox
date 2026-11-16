"""Regressions: each bug that reached main or a review, so it cannot come back. One line per bug, here or where
its test lives:

  withdrawn pull request kept its early-PR bonus ..... test_grading: test_a_withdrawn_pull_request_gives_up_its_early_bonus
  a queued grading run started from a stale commit ... simulate_workflows: "a run that waited starts from the latest results"
  a lesson key could be a header alias (github) ...... test_lessons: test_a_key_cannot_be_a_column_the_board_already_has
  a blank optional form field became the word None ... test_slices: test_a_blank_optional_field_is_empty_not_the_word_none
  the facilitator page showed nothing once every
  change was undone ................................... test_facilitator_browser: test_add_rename_merge_and_undo_them_all
  the pre-commit hook let tests run git against this
  repository (it set core.bare and a fake user) ...... below
  a failed save left a history entry for a change
  that never happened ................................. below
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'grader'))
import roster  # noqa: E402


class HookTests(unittest.TestCase):
    def test_the_pre_commit_hook_keeps_tests_away_from_this_repository(self):
        """Git exports GIT_DIR and friends to a hook; a test that makes a throwaway repository must not reach ours."""
        hook = (REPO / '.githooks' / 'pre-commit').read_text()
        clear = next((line for line in hook.splitlines() if line.startswith('unset ')), None)
        self.assertIsNotNone(clear, 'the hook must clear git\'s local environment')
        self.assertLess(hook.index(clear), hook.index('unittest'), 'and do it before running the tests')

        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        ours, theirs = work / 'ours', work / 'theirs'
        subprocess.run(['git', 'init', '-q', str(ours)], check=True)
        theirs.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env |= {'GIT_DIR': str(ours / '.git'), 'GIT_INDEX_FILE': str(ours / '.git' / 'index')}  # as git sets them for a hook
        # What a test does after the hook's line: make its own repository and configure it.
        subprocess.run(['bash', '-c', f'{clear}\ncd "{theirs}" && git init -q && git config user.name Author'], env=env, check=True)
        config = (ours / '.git' / 'config').read_text()
        self.assertNotIn('Author', config)
        self.assertRegex(config, re.compile(r'bare = false'))
        self.assertTrue((theirs / '.git').is_dir())


class SaveOrderTests(unittest.TestCase):
    def test_a_save_that_fails_leaves_no_history_entry(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        (root / 'grader').mkdir()
        (root / 'lessons.json').write_text('[{"key": "fizzbuzz", "label": "FizzBuzz", "repo": "o/f", "check": "none"}]')
        (root / 'participants.csv').write_text('name,github_username,fizzbuzz\nAnn,ann,\n')
        board = roster.Roster(root)
        with mock.patch.object(roster._Sheet, 'save', side_effect=OSError('disk full')), self.assertRaises(OSError):
            board.award('Ann', 'helped')
        self.assertEqual(board.history(), [])
        self.assertEqual((root / 'participants.csv').read_text(), 'name,github_username,fizzbuzz\nAnn,ann,\n')


if __name__ == '__main__':
    unittest.main()
