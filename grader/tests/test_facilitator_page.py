"""The facilitator page (facilitator.html) and its practice copy (facilitator_walkthrough.py), and the facilitator
forms (grader/issue_form.FORMS) matching their facilitator-*.yml workflows.

The page sends one Changes issue (changes.js); the one-change forms (issue templates and Actions forms) must ask
for exactly their workflow's inputs. The practice copy must apply changes the way the workflows would, and never
touch this repository.
"""
import hashlib
import json
import re
import shutil
import tempfile
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
import issue_form  # noqa: E402

WORKFLOWS = REPO / '.github' / 'workflows'
FORM_WORKFLOWS = sorted(p.name for p in WORKFLOWS.glob('facilitator-*.yml') if p.name != 'facilitator-action.yml')
PAGE = (REPO / 'facilitator.html').read_text()
SCRIPTS = re.findall(r'<script src="([\w.-]+)"', PAGE)  # the page's own scripts, each a file beside it
STEPS = (REPO / 'walkthrough' / 'facilitator-steps.js').read_text()


def yaml(path):
    out = subprocess.run(['ruby', '-ryaml', '-rjson', '-e', 'puts JSON.generate(YAML.load_file(ARGV[0]))', str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@unittest.skipUnless(shutil.which('ruby'), 'needs Ruby (the YAML)')
class FormsMatchTheWorkflowsTests(unittest.TestCase):
    """issue_form.FORMS lists the facilitator forms: one per facilitator-*.yml, with exactly its inputs."""

    def test_one_form_per_facilitator_workflow(self):
        self.assertEqual(sorted(f'facilitator-{name}.yml' for name, _ in issue_form.FORMS.values()), FORM_WORKFLOWS)

    def test_each_form_asks_for_exactly_its_workflows_inputs(self):
        for title, (name, fields) in issue_form.FORMS.items():
            with self.subTest(title):
                inputs = (yaml(WORKFLOWS / f'facilitator-{name}.yml')['true']['workflow_dispatch'] or {}).get('inputs') or {}
                self.assertEqual([field for _, field in fields], list(inputs))


class PageTests(unittest.TestCase):
    def test_every_tour_step_target_is_on_the_page(self):
        anchors = set(re.findall(r'data-tour="([\w-]+)"', PAGE)) | set(re.findall(r"dataset\.tour = '([\w-]+)'", PAGE))
        targets = set(re.findall(r"target: '([\w-]+)'", STEPS))
        self.assertTrue(targets)
        self.assertEqual(targets - anchors, set(), 'facilitator-steps.js targets missing from facilitator.html')

    def test_neither_page_shows_a_lesson_still_being_checked(self):
        for name in ('index.html', 'facilitator.html'):
            with self.subTest(name):
                self.assertRegex((REPO / name).read_text(), r"\.filter\(\(l\) => l\.status !== 'checking'\)")

    @unittest.skipUnless(shutil.which('node'), 'needs Node.js to read the tour')
    def test_each_tour_step_names_the_tab_its_target_is_on(self):
        from html.parser import HTMLParser

        class Panels(HTMLParser):  # data-tour name -> the tab panel it sits in ('' for none)
            def __init__(self):
                super().__init__()
                self.open, self.where = [], {}

            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                self.open.append((tag, a.get('role') == 'tabpanel' and a.get('id', '').removesuffix('-panel')))
                if 'data-tour' in a:
                    self.where[a['data-tour']] = next((panel for _, panel in reversed(self.open) if panel), '')

            def handle_endtag(self, tag):
                while self.open and self.open.pop()[0] != tag:
                    pass
        panels = Panels()
        panels.feed(PAGE)
        script = "import(process.argv[1]).then((m) => process.stdout.write(JSON.stringify(m.steps({people: [], lessons: []}))))"
        steps = json.loads(subprocess.run(['node', '--input-type=module', '-e', script, (REPO / 'walkthrough' / 'facilitator-steps.js').as_uri()],
                                          capture_output=True, text=True, check=True).stdout)
        for step in (s for s in steps if s.get('target') in panels.where):
            with self.subTest(step['title']):
                self.assertEqual(step.get('tab', ''), panels.where[step['target']], 'the tour opens the tab its target is on')

    def test_the_page_and_every_script_it_loads_are_published_and_in_practice(self):
        publish = (WORKFLOWS / 'pages.yml').read_text()
        self.assertTrue(SCRIPTS)
        for f in ('facilitator.html', *SCRIPTS, 'participants.csv', 'lessons.json'):
            self.assertRegex(publish, rf'cp [^\n]*\b{re.escape(f)}\b', f)
        self.assertLessEqual({'facilitator.html', *SCRIPTS}, set(facilitator_walkthrough.COPY))

    def test_the_page_asks_for_no_token_and_talks_only_to_github(self):
        for name, text in (('facilitator.html', PAGE), *((f, (REPO / f).read_text()) for f in SCRIPTS)):
            with self.subTest(name):
                self.assertNotRegex(text, r'(?i)authorization|type="password"|localStorage\.setItem\(.*token')
                self.assertEqual(re.findall(r'https?://(?!github\.com|api\.github\.com)[\w.-]+', text), [])


class PracticeTrialTests(unittest.TestCase):
    """Practice puts lessons live by the real rule (lesson_lifecycle), with a pretend trial in place of Gradle."""

    def test_a_lesson_added_goes_live_and_the_one_that_failed_its_trial_stays_failed(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        facilitator_walkthrough.practice_copy(root)
        entries = json.loads((root / 'lessons.json').read_text())
        entries.append({'key': 'new_one', 'label': 'New one', 'repo': 'practice/new-one', 'check': 'none', 'status': 'checking',
                        'added': '2026-11-18T09:00:00.000000Z'})
        (root / 'lessons.json').write_text(json.dumps(entries))
        facilitator_walkthrough.PracticeGitHub(root)._grading_run()
        status = {e['key']: e.get('status') for e in json.loads((root / 'lessons.json').read_text())}
        self.assertEqual((status['new_one'], status['old_exercise']), (None, 'checking'))


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

    def send(self, *rows, batch='prac'):
        """What the page's Send does: one Changes issue with these rows. Returns the issue as answered."""
        body = issue_form.batch_body(batch, [list(r) for r in rows])
        status, issue = self.api('/issues', {'title': 'Facilitator: Changes', 'body': body})
        self.assertEqual(status, 201)
        return issue

    def test_starts_with_none_of_the_real_changes(self):
        for name in ('history', 'batches'):  # the real repository's, whatever they hold, stay out of practice
            self.assertEqual(self.api(f'/contents/grader/{name}.json')[0], 404, name)

    def test_serves_the_page_and_example_people(self):
        self.assertEqual(self.call('/facilitator.html')[0], 200)
        self.assertIn(b'Asha Rao', self.call('/participants.csv')[1])
        self.assertEqual(self.call('/practice-api/user')[1], {'login': 'you'})

    def test_a_change_is_made_on_the_copy_only(self):
        issue = self.send(['award', 'Asha Rao', 'helped', '2'], batch='prac-a')
        self.assertEqual((issue['state'], issue['state_reason'], issue['locked']), ('closed', 'completed', True))
        self.assertIn('Gave 2 helps to Asha Rao', issue['answer'])
        self.assertEqual(self.api('/contents/grader/history.json')[1][-1]['by'], 'you')
        self.assertEqual(hashlib.sha256((REPO / 'participants.csv').read_bytes()).hexdigest(), self.real)

    def test_a_mistake_is_answered_with_why_as_on_github(self):
        issue = self.send(['award', 'Nobody Here', 'helped', '1'], batch='prac-b')
        self.assertEqual(issue['state_reason'], 'not_planned')
        self.assertTrue(issue['answer'].startswith('### ❌ Nothing was changed.'), issue['answer'])  # the run page's summary
        self.assertIn('Nobody called "Nobody Here"', issue['answer'])

    def test_undo_reverses_the_practice_change(self):
        before = self.call('/participants.csv')[1]
        self.send(['rename', 'Asha Rao', 'Asha R'], batch='prac-c')
        self.assertEqual(self.send(['undo'], batch='prac-d')['state_reason'], 'completed')
        self.assertEqual(self.call('/participants.csv')[1], before)

    def test_a_changes_issue_is_applied_row_by_row(self):
        rows = [['award', 'Asha Rao', 'helped', '1'], ['award', 'Nobody Here', 'helped', '1']]
        body = issue_form.batch_body('prac1', rows)
        status, issue = self.api('/issues', {'title': 'Facilitator: Changes', 'body': body})
        self.assertEqual((status, issue['state'], issue['state_reason'], issue['locked']), (201, 'closed', 'completed', True))
        batch = self.api('/contents/grader/batches.json')[1]['prac1']
        self.assertEqual([r['ok'] for r in batch['rows']], [True, False])
        self.assertTrue(batch['rows'][0]['change'])

    def test_reading_state_again_unchanged_costs_a_304(self):
        self.send(['award', 'Asha Rao', 'helped', '1'], batch='prac-e')
        req = urllib.request.Request(self.base + '/practice-api/repos/practice/leaderboard/contents/grader/history.json')
        with urllib.request.urlopen(req) as r:
            etag = r.headers['ETag']
        req.add_header('If-None-Match', etag)
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        self.assertEqual(e.exception.code, 304)
        e.exception.close()

    def test_only_issues_can_change_it(self):
        # The page sends issues; nothing in practice starts a workflow, as nothing on the real page does.
        for path in ('/actions/workflows/facilitator-award.yml/dispatches', '/actions/workflows/grade.yml/dispatches'):
            with self.subTest(path):
                self.assertEqual(self.api(path, {'ref': 'main'})[0], 404)
        self.assertEqual(self.api('/actions/workflows/facilitator-award.yml/runs')[0], 404)
        self.assertEqual(self.api('/contents/grader/history.json')[0], 404)  # nothing has run

if __name__ == '__main__':
    unittest.main()
