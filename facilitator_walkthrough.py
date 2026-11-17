"""Opens a walkthrough of the facilitator page in your browser, on a practice copy with made-up people.

    python3 facilitator_walkthrough.py          (Windows: py facilitator_walkthrough.py)       Needs Python 3.8 or newer.

It copies the leaderboard into a temporary folder, puts example people in it (the same ones as walkthrough.py),
and serves it on your own computer only (http://127.0.0.1), with a stand-in for GitHub: changes you send run the
same leaderboard commands changes-from-issues.yml would, on the copy. So every change really works, and
nothing is changed in this folder or sent anywhere. The copy is deleted when you press Ctrl+C.
"""
import argparse
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import traceback
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'grader'))
sys.path.insert(0, str(ROOT))
import lessons  # noqa: E402
import walkthrough  # noqa: E402

REPO = 'practice/leaderboard'  # what facilitator.html?practice calls it
API = '/practice-api'
ACTOR = 'you'
# What the page and the forms need: the pages, the rules, the lessons, the workflows (for their commands) and the grader.
COPY = ['index.html', 'facilitator.html', 'scoring.js', 'lessons.json', 'dashboard.json',
        'walkthrough', 'grader', '.github/workflows']


def practice_results(lessons_):
    """grader/results.json for the example people: the pull requests that earn their early-PR bonus
    (walkthrough.SAMPLE_EARLY), so the bonus stays when a practice change brings graded results in."""
    first, second = lessons_[0], lessons_[min(1, len(lessons_) - 1)]
    opened = [('asha-rao', first, True), ('benok', first, False), ('devpatel', first, False), ('asha-rao', second, True)]
    people = dict((login, name) for name, login in walkthrough.SAMPLE_PEOPLE)
    return {'people': {login: people[login] for login, _, _ in opened}, 'submissions': {
        f'{lesson.repo}#{n}': {'task': lesson.key, 'login': login, 'passed': passed, 'url': f'https://github.com/{lesson.repo}/pull/{n}',
                               'created_at': f'2026-11-02T09:00:{n:02d}Z'}
        for n, (login, lesson, passed) in enumerate(opened, 1)}}


def practice_copy(dest):
    """A copy of the leaderboard at `dest` with the example people and their pull requests, and no history."""
    dest = Path(dest)
    for name in COPY:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=shutil.ignore_patterns('__pycache__', 'tests', 'fixtures', 'results.json', 'history.json', 'batches.json', '.cache'))
        elif src.exists():
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dest / name)
    loaded = lessons.load(dest)
    (dest / 'participants.csv').write_text(walkthrough.sample_csv([l.key for l in loaded]), encoding='utf-8')
    (dest / 'grader' / 'results.json').write_text(json.dumps(practice_results(loaded), indent=2) + '\n', encoding='utf-8')
    return dest


class PracticeGitHub:
    """Just enough of GitHub's API for facilitator.html: opening a facilitator issue (as pressing Submit would), and
    reading grader/history.json and grader/batches.json. An issue is applied straight away, on the practice copy,
    and answered as changes-from-issues.yml would answer it (grader/issue_form.answer)."""

    def __init__(self, root):
        self.root = Path(root)
        self.issues = []
        self.lock = threading.Lock()

    def open_issue(self, title, body):
        """What submitting a facilitator issue does: the same command, answered and closed straight away."""
        import issue_form
        try:
            argv = issue_form.command(title, body)
        except issue_form.NotAForm as e:
            return 422, {'message': str(e)}
        outcome, summary = self._apply(argv)
        reply = issue_form.answer('', summary, outcome)  # the answer changes-from-issues.yml gives
        number = len(self.issues) + 1
        issue = {'number': number, 'title': title, 'state': 'closed', 'locked': bool(reply.lock_reason),
                 'state_reason': reply.state_reason, 'html_url': f'#issue-{number}', 'answer': reply.body}
        self.issues.append(issue)
        return 201, issue

    def _apply(self, argv):
        """(outcome, summary): a leaderboard command run on the practice copy, as the workflow runs it: the outcome
        leaderboard.py settles (changed, refused or broken) and the run page's summary, read as the workflow reads them."""
        import leaderboard  # the copy's grader is the same code; import late so the copy exists first
        out, err = io.StringIO(), io.StringIO()
        with self.lock, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            env = {k: os.environ.pop(k, None) for k in ('GITHUB_STEP_SUMMARY', 'GITHUB_ACTOR', 'LEADERBOARD_OUTCOME')}
            temp = Path(tempfile.mkdtemp())  # outside the copy, like the runner's temp folder
            outcome_file, summary_file = temp / 'outcome', temp / 'summary.md'
            os.environ.update(GITHUB_ACTOR=ACTOR, LEADERBOARD_OUTCOME=str(outcome_file), GITHUB_STEP_SUMMARY=str(summary_file))
            try:
                leaderboard.main(argv, root=self.root)
            except Exception:  # broken: leaderboard.py has recorded it; show why, as a run's log would
                traceback.print_exc(file=sys.__stderr__)
            finally:
                for k in ('GITHUB_ACTOR', 'LEADERBOARD_OUTCOME', 'GITHUB_STEP_SUMMARY'):
                    os.environ.pop(k, None)
                os.environ.update({k: v for k, v in env.items() if v is not None})
            outcome = leaderboard.read_outcome(outcome_file)[0]
            summary = summary_file.read_text(encoding='utf-8').strip() if summary_file.exists() else ''
            shutil.rmtree(temp, ignore_errors=True)
        return outcome, summary  # nothing summarised: issue_form.answer says something went wrong, as on GitHub


class Handler(SimpleHTTPRequestHandler):
    """Serves the practice copy, the walkthrough's context, and the stand-in GitHub API under /practice-api."""

    def __init__(self, *args, github=None, **kwargs):
        self.github = github  # set first: the parent constructor handles the request straight away
        super().__init__(*args, **kwargs)

    def send_json(self, status, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else b''
        self.send_response(status)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        if body is not None:
            self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def api_path(self):
        path = self.path.split('?')[0]
        prefix = f'{API}/repos/{REPO}'
        return path[len(prefix):] if path.startswith(prefix) else None

    def do_GET(self):
        path = self.path.split('?')[0]
        root = Path(self.directory)
        if path == '/walkthrough/context.json':
            return self.send_json(200, context(root))
        if path == f'{API}/user':
            return self.send_json(200, {'login': ACTOR})
        sub = self.api_path()
        if sub == '':
            return self.send_json(200, {'full_name': REPO})
        if sub is not None:
            if m := re.fullmatch(r'/contents/grader/(history|batches)\.json', sub):
                path = root / 'grader' / f'{m.group(1)}.json'
                if not path.exists():
                    return self.send_json(404, {'message': 'Not Found'})
                text = path.read_text(encoding='utf-8')
                etag = '"%x"' % (hash(text) & 0xffffffff)
                if self.headers.get('If-None-Match') == etag:  # as GitHub answers a conditional request
                    self.send_response(304)
                    self.send_header('ETag', etag)
                    self.end_headers()
                    return None
                return self.send_json(200, json.loads(text), {'ETag': etag})
            return self.send_json(404, {'message': 'Not Found'})
        if path.startswith(API):
            return self.send_json(404, {'message': 'Not Found'})
        super().do_GET()

    def do_POST(self):
        sub = self.api_path()
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
        except ValueError:
            return self.send_json(400, {'message': 'Problems parsing JSON'})
        if sub == '/issues':
            status, reply = self.github.open_issue(body.get('title', ''), body.get('body', ''))
            return self.send_json(status, reply)
        self.send_json(404, {'message': 'Not Found'})

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')  # always show the practice copy as it is now
        super().end_headers()

    def log_message(self, *args):
        pass  # keep the terminal quiet


def context(root):
    """What the facilitator tour mentions by name: example people, the lessons, and the real page's address."""
    repo = walkthrough.github_repo(ROOT)
    people = [name for name, _ in walkthrough.SAMPLE_PEOPLE]
    return {'people': people, 'lessons': [{'key': l.key, 'label': l.label} for l in lessons.load(root)],
            'pages_url': f'https://{repo[0].lower()}.github.io/{repo[1]}/' if repo else None}


def serve(port):
    """(server, url, practice folder): the practice copy served on 127.0.0.1."""
    folder = practice_copy(tempfile.mkdtemp(prefix='leaderboard-practice-'))
    server = ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, directory=str(folder), github=PracticeGitHub(folder)))
    return server, f'http://127.0.0.1:{server.server_address[1]}/walkthrough/?tour=facilitator', folder


def main(argv):
    p = argparse.ArgumentParser(description='Practise the facilitator page on made-up people.')
    p.add_argument('--port', type=int, default=8124)
    p.add_argument('--no-open', action='store_true', help='do not open a browser window')
    args = p.parse_args(argv)

    server, url, folder = serve(walkthrough.free_port(args.port))
    print(f'Facilitator walkthrough running at {url}\nPress Ctrl+C to stop.', flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')
    finally:
        server.server_close()
        shutil.rmtree(folder, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
