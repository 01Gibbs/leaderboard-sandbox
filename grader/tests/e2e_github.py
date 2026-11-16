"""End to end on GitHub: the real facilitator workflows on a real leaderboard repository, then all of it undone.

    python3 grader/tests/e2e_github.py --repo 01Gibbs/leaderboard-sandbox            (about 10 minutes)
    python3 grader/tests/e2e_github.py --repo 01Gibbs/leaderboard-sandbox --grade    (also a grading run)

It starts each facilitator-*.yml workflow with the same API call facilitator.html makes, finds the run the way the
page does, waits for it, and checks main's participants.csv changed as it should. A mistake must fail and change
nothing. Then it undoes every change and checks main is back where it started. It needs a token that may run
the workflows (GH_TOKEN, or `gh auth token`). It commits to main, so use it on a repository where that is fine.
Not run by `unittest discover` (the file name does not start with test_).
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
        """What facilitator.html does: dispatch, find the newest run by `me` since the click, follow it to the end."""
        started = time.time()
        self.call('POST', f'/repos/{self.repo}/actions/workflows/{workflow}/dispatches', {'ref': 'main', 'inputs': inputs})
        return self.finish(self.find_run(workflow, 'workflow_dispatch', started, me))

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
    p.add_argument('--grade', action='store_true', help='also send a submission event and wait for the grading run')
    a = p.parse_args(argv)
    token = os.environ.get('GH_TOKEN') or subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True).stdout.strip()
    gh = GitHub(a.repo, token)
    me = gh.me()
    stamp = datetime.now(timezone.utc).strftime('%H%M%S')
    who, dup = f'E2E Check {stamp}', f'E2E Duplicate {stamp}'
    lessons = json.loads(gh.file('lessons.json'))
    lesson = lessons[-1]['key']
    start_csv, start_history = gh.file('participants.csv'), json.loads(gh.file('grader/history.json') or '[]')
    made, failures = 0, []

    def step(title, workflow, inputs, expect_success, check):
        nonlocal made
        run = gh.run_form(workflow, inputs, me)
        ok = run['conclusion'] == 'success'
        made += ok
        sheet = rows(gh.file('participants.csv'))
        problem = None if ok == expect_success else f'run {run["conclusion"]}, expected {"success" if expect_success else "failure"}'
        problem = problem or check(sheet)
        print(f'{"ok  " if not problem else "FAIL"} {title}  ({run["html_url"]})' + (f'\n     {problem}' if problem else ''), flush=True)
        if problem:
            failures.append(title)

    try:
        step('add a person', 'facilitator-add.yml', {'name': who, 'github': ''}, True,
             lambda s: None if who in s else f'{who} is not on the sheet')
        step('award 2 helps', 'facilitator-award.yml', {'person': who, 'kind': 'helped', 'amount': '2'}, True,
             lambda s: None if s[who]['helped'] == '2' else f'helped is {s[who]["helped"]!r}')
        step(f'mark {lesson} correct', 'facilitator-mark.yml', {'person': who, 'lesson': lesson, 'status': 'correct'}, True,
             lambda s: None if s[who][lesson] == 'correct' else f'{lesson} is {s[who][lesson]!r}')
        step('add a duplicate', 'facilitator-add.yml', {'name': dup, 'github': ''}, True,
             lambda s: None if dup in s else f'{dup} is not on the sheet')
        step('merge the duplicate', 'facilitator-merge.yml', {'keep': who, 'duplicate': dup}, True,
             lambda s: None if dup not in s and who in s else 'both rows are still there')
        step('rename', 'facilitator-rename.yml', {'person': who, 'new_name': who + ' R'}, True,
             lambda s: None if who + ' R' in s else 'not renamed')
        step('a misspelt name changes nothing', 'facilitator-award.yml', {'person': 'Nobody ' + stamp, 'kind': 'helped', 'amount': '1'},
             False, lambda s: None if s[who + ' R']['helped'] == '2' else 'the sheet changed')
    finally:
        changes = made  # undo counts as made too, so fix the number first
        for n in range(changes):
            step(f'undo {n + 1} of {changes}', 'facilitator-undo.yml', {}, True, lambda s: None)
        end_csv, end_history = gh.file('participants.csv'), json.loads(gh.file('grader/history.json') or '[]')
        leftovers = [n for n in rows(end_csv) if n.startswith(('E2E Check', 'E2E Duplicate'))]
        changed = {n for n, r in rows(start_csv).items() if rows(end_csv).get(n) != r}
        problem = (f'rows left behind: {leftovers}' if leftovers else
                   f'history has {len(end_history)} entries, started with {len(start_history)}' if len(end_history) != len(start_history) else
                   f'rows differ from the start (a grading run may have raised them meanwhile): {sorted(changed)}' if changed else None)
        print(f'{"ok  " if not problem else "FAIL"} main is back where it started' + (f'\n     {problem}' if problem else ''))
        if problem:
            failures.append('cleanup')

    if a.grade:
        started = time.time()
        gh.call('POST', f'/repos/{a.repo}/dispatches', {'event_type': 'submission', 'client_payload': {'pr': 'e2e_github.py'}})
        run = gh.finish(gh.find_run('grade.yml', 'repository_dispatch', started), every=15)
        ok = run['conclusion'] == 'success'
        print(f'{"ok  " if ok else "FAIL"} a submission event starts a grading run that succeeds  ({run["html_url"]})')
        if not ok:
            failures.append('grading run')

    print(f'\n{"All passed" if not failures else "Failed: " + ", ".join(failures)}')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
