"""Facilitator changes sent as issues (grader/issue_form.py, changes-from-issues.yml, .github/ISSUE_TEMPLATE/).

An issue must turn into exactly the command its Actions form would run, and only for people who may change the
repository, and answered the same way everywhere. The templates, the parser and the workflows must agree.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'grader'))
import issue_form  # noqa: E402

TEMPLATES = REPO / '.github' / 'ISSUE_TEMPLATE'
WORKFLOWS = REPO / '.github' / 'workflows'


ARGS = re.compile(r"^\s*args:\s*'(.*)'\s*$", re.M)
INPUT = re.compile(r'\$\{\{\s*toJSON\(inputs\.(\w+)\)\s*\}\}')


def workflow_command(workflow_text, inputs):
    """The leaderboard command a facilitator-*.yml workflow runs for these form inputs, built from its own `args:`
    line as GitHub would fill it in."""
    m = ARGS.search(workflow_text)
    if not m:
        raise ValueError('not a facilitator form: no args line')
    return [str(v) for v in json.loads(INPUT.sub(lambda i: json.dumps(str(inputs.get(i.group(1), ''))), m.group(1)))]


def body(**values):
    """An issue form's body as GitHub writes it."""
    return '\n\n'.join(f'### {label}\n\n{value or issue_form.NO_RESPONSE}' for label, value in values.items())


def yaml(path):
    out = subprocess.run(['ruby', '-ryaml', '-rjson', '-e', 'puts JSON.generate(YAML.load_file(ARGV[0]))', str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def api(role):
    def fetch(path):
        if role is None:
            raise issue_form.urllib.error.HTTPError(path, 404, "Not Found", {}, io.BytesIO())
        return {'permission': {'maintain': 'write', 'triage': 'read'}.get(role, role), 'role_name': role}
    return fetch


class ReadingTests(unittest.TestCase):
    def test_each_section_and_an_empty_one(self):
        text = body(**{'Person': 'Asha Rao', 'What for': 'helped', 'How many': ''})
        self.assertEqual(issue_form.fields(text), {'Person': 'Asha Rao', 'What for': 'helped', 'How many': ''})
        self.assertEqual(issue_form.fields(text.replace('\n', '\r\n'))['Person'], 'Asha Rao')

    def test_the_command_a_form_asks_for(self):
        self.assertEqual(issue_form.command('Facilitator: Award points', body(**{'Person': 'Asha', 'What for': 'helped', 'How many': ''})),
                         ['award', 'Asha', 'helped', '1'])  # How many left empty: 1, as the Actions form defaults it
        self.assertEqual(issue_form.command('Facilitator: Add a person', body(**{'Full name': 'Pat', 'GitHub username': ''})),
                         ['add', 'Pat', ''])
        self.assertEqual(issue_form.command('Facilitator: Undo the last change', body(**{'Note (optional)': 'oops'})), ['undo'])

    def test_a_changed_title_or_another_issue_is_not_a_form(self):
        for title in ('Award points', 'Facilitator: Delete everyone', 'Bug: the page is slow', None):
            with self.subTest(title), self.assertRaises(issue_form.NotAForm):
                issue_form.command(title, '')

    def test_a_form_matches_its_actions_form_exactly(self):
        """For the same field values, the issue and the Actions form run the same command."""
        for title, (name, inputs) in issue_form.FORMS.items():
            values = {field: f'value {i}' for i, (_, field) in enumerate(inputs)}
            from_issue = issue_form.command('Facilitator: ' + title, body(**{label: values[field] for label, field in inputs}))
            workflow = (WORKFLOWS / f'facilitator-{name}.yml').read_text()
            self.assertEqual(from_issue, workflow_command(workflow, values), title)


class BatchTests(unittest.TestCase):
    """What the facilitator page sends: several changes in one issue."""

    def test_a_changes_issue_is_one_batch_command(self):
        rows = [['award', 'Asha Rao', 'helped', '1'], ['rename', 'benok', 'Ben "B" Okafor'], ['undo', 'c1a2b3']]
        text = body(Batch='ab12', Changes='\n'.join(json.dumps(r) for r in rows))
        self.assertEqual(issue_form.command('Facilitator: Changes', text), ['batch', 'ab12', json.dumps(rows)])

    def test_blank_lines_are_ignored_and_a_line_that_is_not_json_goes_on_for_batch_to_refuse(self):
        self.assertEqual(json.loads(issue_form.command('Facilitator: Changes', body(Batch='ab12', Changes='\n["undo"]\n\n'))[2]),
                         [['undo']])
        self.assertEqual(issue_form.command('Facilitator: Changes', body(Batch='ab12', Changes='give Asha a help')),
                         ['batch', 'ab12', 'give Asha a help'])

    def test_a_batch_from_an_issue_is_applied_like_one_from_the_command_line(self):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        (work / 'grader').mkdir()
        (work / 'lessons.json').write_text('[{"key": "fizzbuzz", "label": "FizzBuzz", "repo": "o/f", "check": "none"}]')
        (work / 'participants.csv').write_text('name,github_username,fizzbuzz\nAsha Rao,asha,\n')
        args = issue_form.command('Facilitator: Changes', body(Batch='ab12', Changes='["award", "Asha Rao", "helped", "2"]'))
        import leaderboard
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(leaderboard.main(['--args-json', json.dumps(args)], root=work), 0)
        self.assertIn('1 of 1 changes made (batch ab12)', out.getvalue())
        import roster
        self.assertEqual(roster.Roster(work).find('Asha Rao')['helped'], '2')


class WorkflowCommandTests(unittest.TestCase):
    def test_built_from_the_workflows_own_args_line(self):
        self.assertEqual(workflow_command((WORKFLOWS / 'facilitator-award.yml').read_text(), {'person': 'Asha "AR" Rao', 'kind': 'helped', 'amount': '2'}),
                         ['award', 'Asha "AR" Rao', 'helped', '2'])
        self.assertEqual(workflow_command((WORKFLOWS / 'facilitator-add.yml').read_text(), {'name': 'Pat'}), ['add', 'Pat', ''])
        self.assertEqual(workflow_command((WORKFLOWS / 'facilitator-undo.yml').read_text(), {}), ['undo'])


class PermissionTests(unittest.TestCase):
    EVENT = {'issue': {'title': 'Facilitator: Award points', 'user': {'login': 'pat'},
                       'body': body(**{'Person': 'Asha', 'What for': 'helped', 'How many': '2'})}}

    def test_collaborators_who_can_write_may_change_it(self):
        for role in ('admin', 'maintain', 'write'):
            with self.subTest(role):
                self.assertEqual(issue_form.decide(self.EVENT, 'o/board', 't', api(role)), (True, ['award', 'Asha', 'helped', '2'], ''))

    def test_anyone_else_is_told_and_nothing_changes(self):
        for role in ('triage', 'read', 'none', None):
            with self.subTest(role):
                allowed, args, reply = issue_form.decide(self.EVENT, 'o/board', 't', api(role))
                self.assertEqual((allowed, args), (False, None))
                self.assertIn('Only the leaderboard\'s collaborators with write access', reply)
                self.assertIn('@pat', reply)

    def test_not_a_form_is_answered_without_asking_github(self):
        event = {'issue': {'title': 'Please add me', 'user': {'login': 'pat'}, 'body': ''}}
        allowed, _, reply = issue_form.decide(event, 'o/board', 't', api=lambda path: self.fail('asked GitHub'))
        self.assertFalse(allowed)
        self.assertIn('not a facilitator form', reply)


class AnswerTests(unittest.TestCase):
    """What the issue gets back: one reply, and closed as completed only when the change was made; always locked."""

    def test_a_change_made_is_completed_with_what_happened(self):
        reply = issue_form.answer('', '### ✅ Gave 1 help to Asha Rao', 'changed', run_url='https://run/1')
        self.assertEqual((reply.close_reason, reply.state_reason, reply.lock_reason), ('completed', 'completed', 'resolved'))
        self.assertEqual(reply.body, '### ✅ Gave 1 help to Asha Rao\n\n[The run that did this](https://run/1)')

    def test_a_refused_change_is_not_planned_and_says_why(self):
        reply = issue_form.answer('', '### ❌ Nothing was changed. Nobody called "Asha"', 'refused')
        self.assertEqual((reply.close_reason, reply.state_reason, reply.lock_reason), ('not planned', 'not_planned', 'resolved'))
        self.assertIn('Nobody called "Asha"', reply.body)

    def test_not_allowed_answers_with_why_and_is_not_planned(self):
        reply = issue_form.answer('Only the leaderboard\'s collaborators with write access can change it.', '', '')
        self.assertEqual(reply.close_reason, 'not planned')
        self.assertTrue(reply.body.startswith('Only the leaderboard'), reply.body)

    def test_a_fault_before_any_summary_still_answers(self):
        for outcome in ('broken', ''):
            with self.subTest(outcome=outcome):
                reply = issue_form.answer('', '', outcome)
                self.assertEqual(reply.close_reason, 'not planned')
                self.assertIn('Something went wrong', reply.body)

    def test_only_changed_completes(self):
        self.assertEqual({o: issue_form.answer('', 'x', o).close_reason for o in ('changed', 'refused', 'broken', '', 'nonsense')},
                         {'changed': 'completed', 'refused': 'not planned', 'broken': 'not planned', '': 'not planned',
                          'nonsense': 'not planned'})


class WorkflowOutputTests(unittest.TestCase):
    def test_outputs_stay_on_their_own_lines_whatever_the_issue_says(self):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        event = {'issue': {'title': 'Facilitator: Rename a person\nallowed=true', 'user': {'login': 'pat'},
                           'body': body(**{'Person': 'Asha\nallowed=true', 'Name to show': 'x"\nargs=["undo"]'})}}
        (work / 'event.json').write_text(json.dumps(event))
        env = {**os.environ, 'GITHUB_EVENT_PATH': str(work / 'event.json'), 'GITHUB_OUTPUT': str(work / 'out'),
               'GITHUB_REPOSITORY': 'o/board', 'GH_TOKEN': 'not-used'}
        code = ('import sys; sys.path.insert(0, "grader"); import issue_form\n'
                'issue_form.permission = lambda *a, **k: "write"\n'
                'issue_form.main()')
        subprocess.run([sys.executable, '-c', code], cwd=REPO, env=env, check=True, capture_output=True)
        lines = (work / 'out').read_text().splitlines()
        self.assertEqual([line.split('=', 1)[0] for line in lines], ['allowed', 'args', 'reply'])
        allowed = dict(line.split('=', 1) for line in lines)
        if allowed['allowed'] == 'true':  # the title with a newline is still read as Rename: the args are one JSON line
            self.assertEqual(json.loads(allowed['args'])[0], 'rename')


@unittest.skipUnless(shutil.which('ruby') and shutil.which('node'), 'needs Ruby (the YAML) and Node.js (the page\'s forms)')
class AgreementTests(unittest.TestCase):
    """One form, three places: the issue template, issue_form.FORMS and facilitator-*.yml."""

    def test_one_template_per_form_with_the_same_title_labels_and_fields(self):
        names = {f.name for f in TEMPLATES.glob('facilitator-*.yml')} - {'facilitator-changes.yml'}  # the batch, below
        self.assertEqual(names, {f'facilitator-{name}.yml' for name, _ in issue_form.FORMS.values()})
        for title, (name, inputs) in issue_form.FORMS.items():
            with self.subTest(title):
                t = yaml(TEMPLATES / f'facilitator-{name}.yml')
                self.assertEqual((t['name'], t['title']), ('Facilitator: ' + title, 'Facilitator: ' + title))
                self.assertIn('facilitator', t['labels'])
                fields = [(b['attributes']['label'], b['id']) for b in t['body'] if b['type'] == 'input' and b['id'] != 'note']
                self.assertEqual(fields, inputs)
                self.assertTrue(all(b['type'] in ('input', 'markdown') for b in t['body']), 'a link can only fill in text fields')

    def test_the_changes_template_is_what_the_parser_reads(self):
        t = yaml(TEMPLATES / 'facilitator-changes.yml')
        self.assertEqual((t['name'], t['title']), ('Facilitator: Changes', 'Facilitator: Changes'))
        fields = [(b['attributes']['label'], b['id']) for b in t['body'] if b['type'] in ('input', 'textarea')]
        self.assertEqual(fields, issue_form.BATCH_FIELDS)
        self.assertNotIn('render', json.dumps(t), 'a rendered textarea would wrap the rows in a code fence')

    def test_each_form_runs_its_workflows_command(self):
        for name, _ in issue_form.FORMS.values():
            self.assertRegex((WORKFLOWS / f'facilitator-{name}.yml').read_text(), rf'args: \'\["{name}"')

    def test_only_collaborators_issues_start_a_run(self):
        read = yaml(WORKFLOWS / 'changes-from-issues.yml')['jobs']['read']['if']
        self.assertIn("startsWith(github.event.issue.title, 'Facilitator: ')", read)
        allowed = json.loads(re.search(r"fromJSON\('(\[.*?\])'\)", read).group(1))
        self.assertEqual(set(allowed), {'OWNER', 'MEMBER', 'COLLABORATOR'})
        self.assertIn('github.event.issue.author_association', read)
        answer = yaml(WORKFLOWS / 'changes-from-issues.yml')['jobs']['answer']['if']
        self.assertIn("needs.read.result == 'success'", answer)  # so a skipped read answers nothing either

    def test_the_issue_is_closed_by_the_changes_outcome_not_its_wording(self):
        answer = next(st for st in yaml(WORKFLOWS / 'changes-from-issues.yml')['jobs']['answer']['steps'] if 'run' in st)
        self.assertEqual(answer['env']['OUTCOME'], '${{ needs.change.outputs.outcome }}')
        self.assertIn('grader/issue_form.py answer', answer['run'])  # it decides; the shell only posts
        self.assertNotRegex(answer['run'], r'(grep|==|!=|startswith)[^\n]*Nothing was changed')  # words only to show

    def test_the_workflow_reads_the_issue_only_through_python(self):
        wf = (WORKFLOWS / 'changes-from-issues.yml').read_text()
        for run in re.findall(r'run: (?:\|\n)?((?:.*\n)+?)(?=\s+- |\Z|\n\s*\n)', wf):
            self.assertNotIn('github.event.issue', run, 'issue fields go through env or the event file, never into a shell')


if __name__ == '__main__':
    unittest.main()
