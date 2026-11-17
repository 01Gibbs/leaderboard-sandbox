"""End to end on GitHub: the real facilitator workflows on a real leaderboard repository, then all of it undone.

    python3 grader/tests/e2e_github.py --repo OWNER/NAME            the Actions forms (about 8 minutes)
    python3 grader/tests/e2e_github.py --repo OWNER/NAME --issues   issues, as the facilitator page sends them
    python3 grader/tests/e2e_github.py --repo OWNER/NAME --all      both, a grading run from a submission event, one
                                                                    started by hand, and the mutation workflow (~25 min)
    add --keep to leave the test's issues and runs in place afterwards

Each kind of change goes through a real workflow, and main's participants.csv is checked after each. A mistake (a
misspelt name) must be refused: its run succeeds, says why, and changes nothing. Then every change is undone, mostly
in one batch so main gets few commits, and main must be back where it started. Every workflow run started meanwhile
(Pages deploys included) must have succeeded: none failed, none cancelled. When everything passed, it deletes the
issues it opened and the facilitator, issue and Pages runs it caused (grading and mutation runs stay); on a failure
it leaves them for you to look at. It needs a token that may run the workflows and delete issues (GH_TOKEN, or
`gh auth token`, as an admin). It commits to main, so use it on a sandbox copy. Not run by `unittest discover`.
"""
import argparse
import base64
import csv
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = 'https://api.github.com'
# The warning facilitator-action.yml raises only when leaderboard.py settles a change as refused: its only warning.
(REFUSED_WARNING,) = re.findall(r'::warning title=([^:]+)::', (Path(__file__).parents[2] / '.github/workflows/facilitator-action.yml')
                                .read_text())


class GitHub:
    def __init__(self, repo, token):
        self.repo, self.token = repo, token
        self.seen = set()  # runs already claimed, so two quick dispatches of one workflow get a run each
        self.issues = []  # every issue this test opened, so it can delete them afterwards

    def call(self, method, path, body=None, accept='application/vnd.github+json'):
        req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Accept': accept, 'Authorization': 'Bearer ' + self.token,
                                              'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            return json.loads(data) if data and 'json' in r.headers.get('Content-Type', '') else data

    def file(self, path):
        """A file on main, as text ('' when it does not exist)."""
        try:
            got = self.call('GET', f'/repos/{self.repo}/contents/{path}?ref=main')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ''
            raise
        return base64.b64decode(got['content']).decode('utf-8')

    def me(self):
        return self.call('GET', '/user')['login']

    def run_form(self, workflow, inputs, me):
        """A facilitator form in the Actions tab: dispatch, find the newest run by `me` since then, follow it to the
        end. Its outcome, as the workflow settled it: changed, refused (the run succeeds, with the warning the
        workflow raises only for a refused outcome) or broken (the run did not succeed)."""
        started = time.time()
        self.call('POST', f'/repos/{self.repo}/actions/workflows/{workflow}/dispatches', {'ref': 'main', 'inputs': inputs})
        run = self.finish(self.find_run(workflow, 'workflow_dispatch', started, me))
        if run['conclusion'] != 'success':
            return run | {'outcome': 'broken'}
        warnings = [a for job in self.call('GET', f'/repos/{self.repo}/actions/runs/{run["id"]}/jobs')['jobs']
                    for a in self.call('GET', job['check_run_url'].removeprefix(API) + '/annotations')]
        refused = any(a.get('title') == REFUSED_WARNING for a in warnings)
        return run | {'outcome': 'refused' if refused else 'changed'}

    def find_run(self, workflow, event, since, actor=None):
        """The newest run of `workflow` for `event` started since `since` (by `actor`, if given) not already claimed.
        GitHub does not say which run a dispatch started, so this is how the page finds it too."""
        for _ in range(40):
            time.sleep(3)
            runs = self.call('GET', f'/repos/{self.repo}/actions/workflows/{workflow}/runs?event={event}&per_page=10')['workflow_runs']
            mine = [r for r in runs if (actor is None or r['actor']['login'] == actor)
                    and _when(r['created_at']) >= since - 60 and r['id'] not in self.seen]
            if mine:
                self.seen.add(mine[0]['id'])
                return mine[0]
        raise AssertionError(f'{workflow}: no {event} run appeared')

    def send_batch(self, batch_id, rows):
        """What the facilitator page's Send does: one Changes issue with every row, answered and closed. Returns
        (the issue, its reply, the batch's record in grader/batches.json)."""
        body = f'### Batch\n\n{batch_id}\n\n### Changes\n\n' + '\n'.join(json.dumps(r) for r in rows)
        issue = self.open_issue('Facilitator: Changes', body)
        for _ in range(60):
            time.sleep(5)
            issue = self.call('GET', f'/repos/{self.repo}/issues/{issue["number"]}')
            if issue['state'] == 'closed':
                break
        else:
            raise AssertionError(f'issue #{issue["number"]} was not answered')
        for _ in range(12):  # the workflow closes the issue, then locks it: give the lock a moment to land
            if issue.get('locked'):
                break
            time.sleep(5)
            issue = self.call('GET', f'/repos/{self.repo}/issues/{issue["number"]}')
        comments = self.call('GET', f'/repos/{self.repo}/issues/{issue["number"]}/comments')
        return issue, comments[-1]['body'] if comments else '', json.loads(self.file('grader/batches.json') or '{}').get(batch_id)

    def open_issue(self, title, body):
        issue = self.call('POST', f'/repos/{self.repo}/issues', {'title': title, 'body': body})
        self.issues.append(issue)
        return issue

    def clean_up(self, since):
        """Delete the issues this test opened and the runs it caused: its facilitator and issue runs, and the Pages
        runs that published its commits. Grading and mutation runs stay: they are real results. Returns the counts."""
        for issue in self.issues:
            self.call('POST', '/graphql', {'query': 'mutation($id: ID!) { deleteIssue(input: {issueId: $id}) { clientMutationId } }',
                                          'variables': {'id': issue['node_id']}})
        ours = [r for r in self.runs_since(since)
                if (r['id'] in self.seen and r['path'].split('/')[-1] not in ('grade.yml', 'mutation.yml'))
                or (r['path'].endswith('/pages.yml') and re.search(r'E2E |e2e-[0-9]', r.get('display_title') or ''))]
        for r in ours:
            self.call('DELETE', f'/repos/{self.repo}/actions/runs/{r["id"]}')
        return len(self.issues), len(ours)

    def send_issue(self, workflow, inputs):
        """What a facilitator does from the page: open the form's issue (as GitHub writes a submitted form), then
        wait until changes-from-issues.yml answers and closes it. Returns a run-like dict for step()."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import issue_form
        title, (_, fields) = next((t, f) for t, f in issue_form.FORMS.items() if f'facilitator-{f[0]}.yml' == workflow)
        body = '\n\n'.join(f'### {label}\n\n{inputs.get(field) or issue_form.NO_RESPONSE}' for label, field in fields) or '### Note (optional)\n\n_No response_'
        started = time.time()
        issue = self.open_issue(issue_form.TITLE_PREFIX + title, body)
        for _ in range(60):
            time.sleep(5)
            issue = self.call('GET', f'/repos/{self.repo}/issues/{issue["number"]}')
            if issue['state'] == 'closed':
                break
        else:
            raise AssertionError(f'issue #{issue["number"]} was not answered')
        comments = self.call('GET', f'/repos/{self.repo}/issues/{issue["number"]}/comments')
        reply = comments[-1]['body'] if comments else ''
        # Closed as completed only when the outcome was changed; otherwise its run says refused (succeeded) or broken.
        run = self.finish(self.find_run('changes-from-issues.yml', 'issues', started, self.me()))
        outcome = ('changed' if issue.get('state_reason') == 'completed' else
                   'refused' if run['conclusion'] == 'success' else 'broken')
        return {'outcome': outcome, 'html_url': issue['html_url'], 'reply': reply}

    def runs_since(self, since):
        """Every workflow run created since `since`, once all of them have finished (up to 20 minutes)."""
        stamp = datetime.fromtimestamp(since - 5, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        for _ in range(80):
            runs = self.call('GET', f'/repos/{self.repo}/actions/runs?created=%3E%3D{stamp}&per_page=100')['workflow_runs']
            if all(r['status'] == 'completed' for r in runs):
                return runs
            time.sleep(15)
        return runs

    def finish(self, run, every=5, limit=45 * 60, start_within=10 * 60):
        """Follow a run to the end. Gives up (AssertionError) on one GitHub never starts (still queued with no job
        after `start_within` seconds: it happens) or that runs past `limit`, instead of waiting forever."""
        began = time.time()
        while run['status'] != 'completed':
            time.sleep(every)
            run = self.call('GET', f'/repos/{self.repo}/actions/runs/{run["id"]}')
            waited = time.time() - began
            if run['status'] == 'queued' and waited > start_within and not self.call(
                    'GET', f'/repos/{self.repo}/actions/runs/{run["id"]}/jobs')['jobs']:
                raise AssertionError(f'GitHub never started {run["html_url"]} ({int(waited)}s queued, no jobs)')
            if waited > limit:
                raise AssertionError(f'{run["html_url"]} still {run["status"]} after {int(waited)}s')
        return run


def _when(stamp):
    return datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()


def rows(text):
    return {r['name']: r for r in csv.DictReader(io.StringIO(text))}


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--repo', required=True)
    p.add_argument('--issues', action='store_true', help='issues, as the facilitator page sends them, instead of the Actions forms')
    p.add_argument('--all', action='store_true', help='the Actions forms and issues, grading runs, and the mutation workflow')
    p.add_argument('--keep', action='store_true', help="leave the test's issues and runs in place afterwards")
    a = p.parse_args(argv)
    began = time.time()
    token = os.environ.get('GH_TOKEN') or subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True).stdout.strip()
    gh = GitHub(a.repo, token)
    me = gh.me()
    stamp = datetime.now(timezone.utc).strftime('%H%M%S')
    lesson = json.loads(gh.file('lessons.json'))[-1]['key']
    start = Start(gh.file('participants.csv'), json.loads(gh.file('grader/history.json') or '[]'))
    failures = []
    if a.all or not a.issues:
        print('\n--- Changes through the Actions forms')
        failures += actions_journey(gh, me, f'{stamp}a', lesson, start)
    if a.all or a.issues:
        print('\n--- Changes sent as issues, as the facilitator page sends them')
        failures += issues_journey(gh, f'{stamp}i', lesson, start)

    if a.all:
        print('\n--- Grading and the other workflows')
        started = time.time()
        gh.call('POST', f'/repos/{a.repo}/dispatches', {'event_type': 'submission', 'client_payload': {'pr': 'e2e_github.py'}})
        run = gh.finish(gh.find_run('grade.yml', 'repository_dispatch', started), every=15)
        failures += report('a submission event starts a grading run that succeeds', run['conclusion'] == 'success', run['html_url'])
        started = time.time()
        gh.call('POST', f'/repos/{a.repo}/actions/workflows/grade.yml/dispatches', {'ref': 'main'})
        run = gh.finish(gh.find_run('grade.yml', 'workflow_dispatch', started, me), every=15)
        failures += report('Grade submissions started by hand succeeds', run['conclusion'] == 'success', run['html_url'])
        started = time.time()
        gh.call('POST', f'/repos/{a.repo}/actions/workflows/mutation.yml/dispatches', {'ref': 'main'})
        run = gh.finish(gh.find_run('mutation.yml', 'workflow_dispatch', started, me), every=30)
        failures += report('mutation testing: every mutant caught', run['conclusion'] == 'success', run['html_url'])

    print('\n--- Every workflow run started meanwhile')
    runs = gh.runs_since(began)
    bad = [f'{r["name"]} [{r["event"]}] {r["conclusion"] or r["status"]}: {r["html_url"]}' for r in runs if r['conclusion'] != 'success']
    failures += report(f'all {len(runs)} runs succeeded: none failed, none cancelled', not bad, '\n     '.join(bad))

    if failures or a.keep:
        print(f'\nLeft in place to look at: {len(gh.issues)} issues and the runs above.')
    else:
        issues, deleted = gh.clean_up(began)
        print(f'\nLeft no trace: deleted {issues} issues and {deleted} runs. Its commits stay on main.')
    print(f'\n{"All passed" if not failures else "Failed: " + ", ".join(failures)}')
    return 1 if failures else 0


class Start:
    """main as it was before the test: participants.csv and grader/history.json."""

    def __init__(self, csv_text, history):
        self.csv, self.history = csv_text, history

    def problem(self, gh):
        """None when main is back where it started; otherwise what differs."""
        end_csv, end_history = gh.file('participants.csv'), json.loads(gh.file('grader/history.json') or '[]')
        leftovers = [n for n in rows(end_csv) if n.startswith('E2E ')]
        changed = {n for n, r in rows(self.csv).items() if rows(end_csv).get(n) != r}
        return (f'rows left behind: {leftovers}' if leftovers else
                f'history has {len(end_history)} entries, started with {len(self.history)}' if len(end_history) != len(self.history) else
                f'rows differ from the start (a grading run may have raised them meanwhile): {sorted(changed)}' if changed else None)

    def new_changes(self, gh):
        """The ids of the changes made since the start, newest first: what to undo."""
        history = json.loads(gh.file('grader/history.json') or '[]')
        return [h['id'] for h in reversed(history[len(self.history):])]


def report(title, ok, detail=''):
    print(f'{"ok  " if ok else "FAIL"} {title}' + (f'  ({detail})' if ok and detail else f'\n     {detail}' if detail else ''), flush=True)
    return [] if ok else [title]


def undo_all(gh, start, batch_id):
    """Undo every change made since the start in one batch issue: one commit on main. Returns failures."""
    ids = start.new_changes(gh)
    if not ids:
        return report('nothing to undo', True)
    issue, reply, record = gh.send_batch(batch_id, [['undo', i] for i in ids])
    made = [r['ok'] for r in (record or {}).get('rows', [])]
    return report(f'undo the other {len(ids)} changes in one batch', made == [True] * len(ids), reply.splitlines()[0] if reply else 'no reply')


def actions_journey(gh, me, stamp, lesson, start):
    """Each Actions form once, checked on main; the Undo form once; the rest undone in one batch."""
    who, dup = f'E2E Check {stamp}', f'E2E Duplicate {stamp}'
    failures = []

    def step(title, workflow, inputs, expect, check):
        try:
            run = gh.run_form(workflow, inputs, me)
        except AssertionError as e:  # a run that never started or never ended: report it, carry on to the undo
            run = {'outcome': 'broken', 'html_url': str(e)}
        problem = None if run['outcome'] == expect else f'{run["outcome"]}, expected {expect}'
        problem = problem or check(rows(gh.file('participants.csv')))
        failures.extend(report(title, not problem, problem or run['html_url']))

    try:
        step('add a person', 'facilitator-add.yml', {'name': who, 'github': ''}, 'changed',
             lambda s: None if who in s else f'{who} is not on the sheet')
        step('award 2 helps', 'facilitator-award.yml', {'person': who, 'kind': 'helped', 'amount': '2'}, 'changed',
             lambda s: None if s[who]['helped'] == '2' else f'helped is {s[who]["helped"]!r}')
        step(f'mark {lesson} correct', 'facilitator-mark.yml', {'person': who, 'lesson': lesson, 'status': 'correct'}, 'changed',
             lambda s: None if s[who][lesson] == 'correct' else f'{lesson} is {s[who][lesson]!r}')
        step('add a duplicate', 'facilitator-add.yml', {'name': dup, 'github': ''}, 'changed',
             lambda s: None if dup in s else f'{dup} is not on the sheet')
        step('merge the duplicate', 'facilitator-merge.yml', {'keep': who, 'duplicate': dup}, 'changed',
             lambda s: None if dup not in s and who in s else 'both rows are still there')
        step('rename', 'facilitator-rename.yml', {'person': who, 'new_name': who + ' R'}, 'changed',
             lambda s: None if who + ' R' in s else 'not renamed')
        step('a misspelt name changes nothing', 'facilitator-award.yml', {'person': 'Nobody ' + stamp, 'kind': 'helped', 'amount': '1'},
             'refused', lambda s: None if s[who + ' R']['helped'] == '2' else 'the sheet changed')
        step('the Undo form reverses the latest change', 'facilitator-undo.yml', {}, 'changed',
             lambda s: None if who in s and who + ' R' not in s else 'the rename was not undone')
    finally:
        failures += undo_all(gh, start, f'e2e-{stamp}-undo')
        problem = start.problem(gh)
        failures += report('main is back where it started', not problem, problem or '')
    return failures


def issues_journey(gh, stamp, lesson, start):
    """One issue from a single form's template (refused); then every kind of change in one batch issue, as the page
    sends them, with a mistake among them; then all undone in one more."""
    who, dup = f'E2E Check {stamp}', f'E2E Duplicate {stamp}'
    failures = []
    try:
        answered = gh.send_issue('facilitator-award.yml', {'person': 'Nobody ' + stamp, 'kind': 'helped', 'amount': '1'})
        failures += report("a form's own issue: a misspelt name is answered, closed as not planned, nothing changed",
                           answered['outcome'] == 'refused' and not start.new_changes(gh), answered['html_url'])
        issue, reply, record = gh.send_batch(f'e2e-{stamp}', [
            ['add', who, ''], ['award', who, 'helped', '2'], ['mark', who, lesson, 'correct'], ['add', dup, ''],
            ['merge', who, dup], ['award', 'Nobody ' + stamp, 'helped', '1'], ['rename', who, who + ' R']])
        failures += report('one issue for all of them: answered, closed as done and locked',
                           issue.get('state_reason') == 'completed' and issue.get('locked') is True, issue['html_url'])
        failures += report('each row has its own outcome: six made, the misspelt name not',
                           [r['ok'] for r in (record or {}).get('rows', [])] == [True] * 5 + [False, True],
                           reply.splitlines()[0] if reply else 'no reply')
        sheet = rows(gh.file('participants.csv')).get(who + ' R', {})
        failures += report('the sheet shows them all', sheet.get('helped') == '2' and sheet.get(lesson) == 'correct'
                           and dup not in rows(gh.file('participants.csv')), str(sheet))
    finally:
        failures += undo_all(gh, start, f'e2e-{stamp}-undo')
        problem = start.problem(gh)
        failures += report('main is back where it started', not problem, problem or '')
    return failures


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
