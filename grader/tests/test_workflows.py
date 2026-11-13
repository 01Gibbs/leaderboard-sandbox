"""The GitHub Actions workflows, run locally by simulate_workflows.py. Needs git and Ruby (to read the YAML)."""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GRADER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GRADER))
import roster  # noqa: E402
import submissions  # noqa: E402


class SavedFilesTests(unittest.TestCase):
    def test_the_workflows_commit_exactly_the_files_the_grader_writes(self):
        root = Path(tempfile.mkdtemp())
        board, subs = roster.Roster(root), submissions.Submissions(root)
        owned = {board.csv_file, board.history_file, subs.file}
        listed = re.search(r'for f in (.+); do', (GRADER / 'run_and_push.sh').read_text()).group(1).split()
        self.assertEqual({root / f for f in listed}, owned)
        root.rmdir()


@unittest.skipUnless(shutil.which('ruby') and shutil.which('git'), 'needs git and Ruby')
class WorkflowTests(unittest.TestCase):
    def test_facilitator_and_publish_workflows(self):
        script = Path(__file__).with_name('simulate_workflows.py')
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('workflow checks passed', r.stdout)


if __name__ == '__main__':
    unittest.main()
