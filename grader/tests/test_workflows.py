"""The GitHub Actions workflows, run locally by simulate_workflows.py. Needs git and Ruby (to read the YAML)."""
import json
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiers import slow  # noqa: E402


class SavedFilesTests(unittest.TestCase):
    def test_the_workflows_commit_exactly_the_files_the_grader_writes(self):
        root = Path(tempfile.mkdtemp())
        board, subs = roster.Roster(root), submissions.Submissions(root)
        owned = {board.csv_file, board.history_file, subs.file}
        listed = re.search(r'for f in (.+); do', (GRADER / 'run_and_push.sh').read_text()).group(1).split()
        self.assertEqual({root / f for f in listed}, owned)
        root.rmdir()


WORKFLOWS = GRADER.parent / '.github' / 'workflows'


def yaml(path):
    out = subprocess.run(['ruby', '-ryaml', '-rjson', '-e', 'puts JSON.generate(YAML.load_file(ARGV[0]))', str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@unittest.skipUnless(shutil.which('ruby'), 'needs Ruby to read the YAML')
class WorkflowRulesTests(unittest.TestCase):
    """Security rules every workflow keeps. One edit to a workflow file could otherwise undo them silently."""

    @classmethod
    def setUpClass(cls):
        cls.workflows = {p.name: yaml(p) for p in sorted(WORKFLOWS.glob('*.yml'))}

    def jobs(self):
        for name, wf in self.workflows.items():
            for job_id, job in wf['jobs'].items():
                yield f'{name}/{job_id}', wf, job

    def test_the_job_that_runs_pull_request_code_can_only_read(self):
        grade = self.workflows['grade.yml']['jobs']['grade']
        self.assertEqual(grade['permissions'], {'contents': 'read'})
        checkout = next(s for s in grade['steps'] if str(s.get('uses', '')).startswith('actions/checkout'))
        self.assertIs(checkout['with']['persist-credentials'], False)
        self.assertNotIn('secrets', json.dumps(grade), 'no secrets in the job that runs participant code')

    def test_saving_jobs_push_with_the_deploy_key_not_the_token(self):
        for name, job in [('facilitator-action.yml', self.workflows['facilitator-action.yml']['jobs']['change']),
                          ('grade.yml', self.workflows['grade.yml']['jobs']['publish'])]:
            self.assertEqual(job['permissions'], {'contents': 'read'}, name)
        for name, wf in self.workflows.items():
            if name.startswith('facilitator-') and name != 'facilitator-action.yml':
                self.assertEqual(wf['permissions'], {'contents': 'read'}, name)

    def test_form_inputs_never_reach_a_shell(self):
        for where, _, job in self.jobs():
            for step in job.get('steps', []):
                self.assertNotRegex(step.get('run', ''), r'\$\{\{\s*(github\.event\.)?inputs\.', f'{where}: pass inputs through env')

    def test_no_workflow_runs_with_the_base_repository_token_on_pull_requests(self):
        for name, wf in self.workflows.items():
            self.assertNotIn('pull_request_target', wf['true'], name)  # YAML 1.1 reads the key `on:` as true

    def test_every_job_states_its_permissions(self):
        for where, wf, job in self.jobs():
            self.assertTrue('permissions' in job or 'permissions' in wf, f'{where} inherits the default token permissions')

    def test_actions_are_pinned_to_a_commit(self):
        # A tag can be moved to other code; a commit cannot. Dependabot (.github/dependabot.yml) proposes updates.
        for where, _, job in self.jobs():
            for step in job.get('steps', []):
                if 'uses' in step:
                    self.assertRegex(step['uses'], r'^[\w.-]+/[\w./-]+@[0-9a-f]{40}$', f'{where}: pin {step["uses"]} to a commit')

    def test_jobs_run_on_a_pinned_runner_image(self):
        for where, _, job in self.jobs():
            if 'runs-on' in job:
                self.assertRegex(job['runs-on'], r'^ubuntu-\d+\.\d+$', f'{where}: pin the image, not ubuntu-latest')


@slow
@unittest.skipUnless(shutil.which('ruby') and shutil.which('git'), 'needs git and Ruby')
class WorkflowTests(unittest.TestCase):
    def test_facilitator_and_publish_workflows(self):
        script = Path(__file__).with_name('simulate_workflows.py')
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('workflow checks passed', r.stdout)


if __name__ == '__main__':
    unittest.main()
