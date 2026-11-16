"""End to end on GitHub: the real facilitator workflows on a real leaderboard repository, then all of it undone.

    python3 grader/tests/e2e_github.py --repo OWNER/NAME                  the Actions forms (about 10 minutes)
    python3 grader/tests/e2e_github.py --repo OWNER/NAME --issues         the same changes as issues, as the page sends them
    python3 grader/tests/e2e_github.py --repo OWNER/NAME --all            both, a grading run from a submission event, one
                                                                          started by hand, and the mutation workflow (~30 min)

Each change goes through a real workflow, and main's participants.csv is checked after each. A mistake (a misspelt
name) must be refused: its run succeeds, says "Nothing was changed", and changes nothing. Then every change is
undone and main must be back where it started. Last, every workflow run started meanwhile (Pages deploys included)
must have succeeded: none failed, none cancelled. It needs a token that may run the workflows (GH_TOKEN, or
`gh auth token`). It commits to main, so use it on a repository where that is fine. Not run by `unittest discover`.
"""
import argparse
import base64
import csv
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = 'https://api.github.com'


class GitHub:
    def __init__(self, repo, token):
        self.repo, self.token = repo, token
        self.seen = set()  # runs already claimed, so two quick dispatches of one workflow get a run each

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
        end. Its outcome: changed, refused (succeeded with a "Nothing was changed" warning) or broken (did not succeed)."""
        started = time.time()
        self.call('POST', f'/repos/{self.repo}/actions/workflows/{workflow}/dispatches', {'ref': 'main', 'inputs': inputs})
        run = self.finish(self.find_run(workflow, 'workflow_dispatch', started, me))
        if run['conclusion'] != 'success':
            return run | {'outcome': 'broken'}
        warnings = [a for job in self.call('GET', f'/repos/{self.repo}/actions/runs/{run["id"]}/jobs')['jobs']
                    for a in self.call('GET', job['check_run_url'].removeprefix(API) + '/annotations')]
        refused = any(a.get('title') == 'Nothing was changed' for a in warnings)
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

    def send_issue(self, workflow, inputs):
        """What a facilitator does from the page: open the form's issue (as GitHub writes a submitted form), then
        wait until changes-from-issues.yml answers and closes it. Returns a run-like dict for step()."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import issue_form
        title, (_, fields) = next((t, f) for t, f in issue_form.FORMS.items() if f'facilitator-{f[0]}.yml' == workflow)
        body = '\n\n'.join(f'### {label}\n\n{inputs.get(field) or issue_form.NO_RESPONSE}' for label, field in fields) or '### Note (optional)\n\n_No response_'
        issue = self.call('POST', f'/repos/{self.repo}/issues', {'title': issue_form.TITLE_PREFIX + title, 'body': body})
        for _ in range(60):
            time.sleep(5)
            issue = self.call('GET', f'/repos/{self.repo}/issues/{issue["number"]}')
            if issue['state'] == 'closed':
                break
        else:
            raise AssertionError(f'issue #{issue["number"]} was not answered')
        comments = self.call('GET', f'/repos/{self.repo}/issues/{issue["number"]}/comments')
        reply = comments[-1]['body'] if comments else ''
        outcome = ('changed' if issue.get('state_reason') == 'completed' and 'Nothing was changed' not in reply else
                   'refused' if 'Nothing was changed' in reply else 'broken')
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

    def finish(self, run, every=5):
        while run['status'] != 'completed':
            time.sleep(every)
            run = self.call('GET', f'/repos/{self.repo}/actions/runs/{run["id"]}')
        return run


def _when(stamp):
    return datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()


def rows(text):
    return {r['name']: r for r in csv.DictReader(io.StringIO(text))}


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--repo', required=True)
    p.add_argument('--issues', action='store_true', help='send each change as an issue, as the facilitator page does')
    p.add_argument('--all', action='store_true', help='Actions forms and issues, grading runs, and the mutation workflow')
    a = p.parse_args(argv)
    began = time.time()
    token = os.environ.get('GH_TOKEN') or subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True).stdout.strip()
    gh = GitHub(a.repo, token)
    me = gh.me()
    stamp = datetime.now(timezone.utc).strftime('%H%M%S')
    lessons = json.loads(gh.file('lessons.json'))
    lesson = lessons[-1]['key']
    start_csv, start_history = gh.file('participants.csv'), json.loads(gh.file('grader/history.json') or '[]')
    failures = []
    for via in (['actions', 'issues'] if a.all else ['issues' if a.issues else 'actions']):
        print(f'\n--- Changes through {"issues, as the facilitator page sends them" if via == "issues" else "the Actions forms"}')
        failures += journey(gh, me, via, f'{stamp}{via[0]}', lesson, start_csv, start_history)

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

    print(f'\n{"All passed" if not failures else "Failed: " + ", ".join(failures)}')
    return 1 if failures else 0


def report(title, ok, detail=''):
    print(f'{"ok  " if ok else "FAIL"} {title}' + (f'  ({detail})' if ok and detail else f'\n     {detail}' if detail else ''), flush=True)
    return [] if ok else [title]


def journey(gh, me, via, stamp, lesson, start_csv, start_history):
    """Each kind of change, through `via` (the Actions forms or issues), checked on main; then all undone."""
    who, dup = f'E2E Check {stamp}', f'E2E Duplicate {stamp}'
    made, failures = 0, []

    def step(title, workflow, inputs, expect, check):
        nonlocal made
        run = gh.send_issue(workflow, inputs) if via == 'issues' else gh.run_form(workflow, inputs, me)
        made += run['outcome'] == 'changed'
        problem = None if run['outcome'] == expect else f'{run["outcome"]}, expected {expect}'
        problem = problem or check(rows(gh.file('participants.csv')))
        failures.extend(report(title, not problem, problem or run['html_url']))

    try:
        step('add a person', 'facilitator-add.yml', {'name': who, 'github': ''}, 'changed',
             lambda s: None if who in s else f'{who} is not on the sheet')
        step('award 2 helps', 'facilitator-award.yml', {'person': who, 'kind': 'helped', 'amount': '2'},  'changed',
             lambda s: None if s[who]['helped'] == '2' else f'helped is {s[who]["helped"]!r}')
        step(f'mark {lesson} correct', 'facilitator-mark.yml', {'person': who, 'lesson': lesson, 'status': 'correct'},  'changed',
             lambda s: None if s[who][lesson] == 'correct' else f'{lesson} is {s[who][lesson]!r}')
        step('add a duplicate', 'facilitator-add.yml', {'name': dup, 'github': ''},  'changed',
             lambda s: None if dup in s else f'{dup} is not on the sheet')
        step('merge the duplicate', 'facilitator-merge.yml', {'keep': who, 'duplicate': dup},  'changed',
             lambda s: None if dup not in s and who in s else 'both rows are still there')
        step('rename', 'facilitator-rename.yml', {'person': who, 'new_name': who + ' R'},  'changed',
             lambda s: None if who + ' R' in s else 'not renamed')
        step('a misspelt name changes nothing', 'facilitator-award.yml', {'person': 'Nobody ' + stamp, 'kind': 'helped', 'amount': '1'},
             'refused', lambda s: None if s[who + ' R']['helped'] == '2' else 'the sheet changed')
    finally:
        changes = made  # undo counts as made too, so fix the number first
        for n in range(changes):
            step(f'undo {n + 1} of {changes}', 'facilitator-undo.yml', {}, 'changed', lambda s: None)
        end_csv, end_history = gh.file('participants.csv'), json.loads(gh.file('grader/history.json') or '[]')
        leftovers = [n for n in rows(end_csv) if n.startswith(('E2E Check', 'E2E Duplicate'))]
        changed = {n for n, r in rows(start_csv).items() if rows(end_csv).get(n) != r}
        problem = (f'rows left behind: {leftovers}' if leftovers else
                   f'history has {len(end_history)} entries, started with {len(start_history)}' if len(end_history) != len(start_history) else
                   f'rows differ from the start (a grading run may have raised them meanwhile): {sorted(changed)}' if changed else None)
        failures.extend(report('main is back where it started', not problem, problem or ''))
    return failures


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
