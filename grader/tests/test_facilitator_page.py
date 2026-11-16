"""The facilitator page (facilitator.html, facilitator-forms.js) and its practice copy (facilitator_walkthrough.py).

The page starts the facilitator-*.yml workflows, so its forms must ask for exactly their inputs. The practice
copy must run each form the way its workflow would, and never touch this repository.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'grader'))
import facilitator_walkthrough  # noqa: E402

WORKFLOWS = REPO / '.github' / 'workflows'
FORM_WORKFLOWS = sorted(p.name for p in WORKFLOWS.glob('facilitator-*.yml') if p.name != 'facilitator-action.yml')
PAGE = (REPO / 'facilitator.html').read_text()
STEPS = (REPO / 'walkthrough' / 'facilitator-steps.js').read_text()


def forms():
    """FORMS from facilitator-forms.js, run the way the browser runs it."""
    script = "const vm = require('vm'), fs = require('fs'); const ctx = {}; vm.createContext(ctx);" \
             "vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx); process.stdout.write(JSON.stringify(vm.runInContext('FORMS', ctx)));"
    return json.loads(subprocess.run(['node', '-e', script, str(REPO / 'facilitator-forms.js')], capture_output=True, text=True, check=True).stdout)


def yaml(path):
    out = subprocess.run(['ruby', '-ryaml', '-rjson', '-e', 'puts JSON.generate(YAML.load_file(ARGV[0]))', str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@unittest.skipUnless(shutil.which('node') and shutil.which('ruby'), 'needs Node.js (the forms) and Ruby (the YAML)')
class FormsMatchTheWorkflowsTests(unittest.TestCase):
    def test_one_form_per_facilitator_workflow(self):
        self.assertEqual(sorted(f['workflow'] for f in forms()), FORM_WORKFLOWS)

    def test_each_form_asks_for_exactly_its_workflows_inputs(self):
        for form in forms():
            with self.subTest(form['workflow']):
                inputs = (yaml(WORKFLOWS / form['workflow'])['true']['workflow_dispatch'] or {}).get('inputs') or {}
                fields = {f['input']: f for f in form['fields']}
                self.assertEqual(set(fields), set(inputs))
                for name, spec in inputs.items():
                    if spec.get('type') == 'choice':
                        self.assertEqual(fields[name]['options'], spec['options'], name)
                    else:
                        self.assertEqual(bool(fields[name].get('required')), bool(spec.get('required')), name)


class PageTests(unittest.TestCase):
    def test_every_tour_step_target_is_on_the_page(self):
        anchors = set(re.findall(r'data-tour="([\w-]+)"', PAGE))
        anchors |= {'form-' + i for i in re.findall(r"id: '(\w+)'", (REPO / 'facilitator-forms.js').read_text())}
        targets = set(re.findall(r"target: '([\w-]+)'", STEPS))
        self.assertTrue(targets)
        self.assertEqual(targets - anchors, set(), 'facilitator-steps.js targets missing from facilitator.html')

    def test_the_page_is_published_with_the_leaderboard(self):
        publish = (WORKFLOWS / 'pages.yml').read_text()
        for f in ('facilitator.html', 'facilitator-forms.js', 'scoring.js', 'participants.csv', 'lessons.json'):
            self.assertRegex(publish, rf'cp [^\n]*\b{re.escape(f)}\b', f)

    def test_the_page_asks_for_no_token_and_talks_only_to_github(self):
        self.assertNotRegex(PAGE, r'(?i)authorization|type="password"|localStorage\.setItem\(.*token')
        self.assertEqual(re.findall(r'https?://(?!github\.com|api\.github\.com)[\w.-]+', PAGE), [])


class CommandTests(unittest.TestCase):
    def test_built_from_the_workflows_own_args_line(self):
        text = (WORKFLOWS / 'facilitator-award.yml').read_text()
        self.assertEqual(facilitator_walkthrough.command(text, {'person': 'Asha "AR" Rao', 'kind': 'helped', 'amount': '2'}),
                         ['award', 'Asha "AR" Rao', 'helped', '2'])
        self.assertEqual(facilitator_walkthrough.command((WORKFLOWS / 'facilitator-add.yml').read_text(), {'name': 'Pat'}), ['add', 'Pat', ''])
        self.assertEqual(facilitator_walkthrough.command((WORKFLOWS / 'facilitator-undo.yml').read_text(), {}), ['undo'])


class PracticeServerTests(unittest.TestCase):
    def setUp(self):
        self.real = hashlib.sha256((REPO / 'participants.csv').read_bytes()).hexdigest()
        self.server, url, self.folder = facilitator_walkthrough.serve(0)
        self.base = url.split('/walkthrough/')[0]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None,
                                     method='POST' if body is not None else 'GET')
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
                return r.status, json.loads(data) if data and 'json' in r.headers.get('Content-Type', '') else data
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read() or b'null')

    def api(self, path, body=None):
        return self.call(f'/practice-api/repos/practice/leaderboard{path}', body)

    def dispatch(self, workflow, **inputs):
        self.assertEqual(self.api(f'/actions/workflows/{workflow}/dispatches', {'ref': 'main', 'inputs': inputs})[0], 204)
        return self.api(f'/actions/workflows/{workflow}/runs')[1]['workflow_runs'][0]

    def test_serves_the_page_and_example_people(self):
        self.assertEqual(self.call('/facilitator.html')[0], 200)
        self.assertIn(b'Asha Rao', self.call('/participants.csv')[1])
        self.assertEqual(self.call('/practice-api/user')[1], {'login': 'you'})

    def test_a_form_runs_its_command_on_the_copy_only(self):
        run = self.dispatch('facilitator-award.yml', person='Asha Rao', kind='helped', amount='2')
        self.assertEqual((run['status'], run['conclusion']), ('completed', 'success'))
        self.assertIn('Gave 2 helps to Asha Rao', run['summary'])
        self.assertEqual(self.api(f'/actions/runs/{run["id"]}')[1]['id'], run['id'])
        self.assertEqual(self.api('/contents/grader/history.json')[1][-1]['by'], 'you')
        self.assertEqual(hashlib.sha256((REPO / 'participants.csv').read_bytes()).hexdigest(), self.real)

    def test_a_mistake_fails_and_says_why(self):
        run = self.dispatch('facilitator-award.yml', person='Nobody Here', kind='helped', amount='1')
        self.assertEqual(run['conclusion'], 'failure')
        self.assertIn('Nobody called "Nobody Here"', run['summary'])

    def test_undo_reverses_the_practice_change(self):
        before = self.call('/participants.csv')[1]
        self.dispatch('facilitator-rename.yml', person='Asha Rao', new_name='Asha R')
        self.assertEqual(self.dispatch('facilitator-undo.yml')['conclusion'], 'success')
        self.assertEqual(self.call('/participants.csv')[1], before)

    def test_only_facilitator_forms_can_be_run(self):
        for workflow in ('grade.yml', 'facilitator-action.yml', '..%2Fgrade.yml'):
            with self.subTest(workflow):
                self.assertIn(self.api(f'/actions/workflows/{workflow}/dispatches', {'ref': 'main'})[0], (404, 422))
        self.assertEqual(self.api('/contents/grader/history.json')[0], 404)  # nothing has run


if __name__ == '__main__':
    unittest.main()
