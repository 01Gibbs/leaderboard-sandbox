"""Grading: find each lesson's pull requests and grade every commit not graded yet.

Results are recorded in Submissions (grader/results.json), which also decides whether an earlier result
still counts; the Roster brings them onto the leaderboard. The rules people rely on live here:
  - a grader error (not the participant's fault) is recorded as passed=None and retried next run;
  - one repository being unreachable skips that repository, not the run;
  - a check module that cannot be loaded (a mistake in it) skips that check's lessons, not the run, with or
    without --no-run (a result's version includes its check's code, so even recording one needs the check).

Pull requests come from a source: GitHub in production, an in-memory one in tests.
"""
import json
import os
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import NamedTuple

import checks
import executor
import lessons
import submissions
import trial


class PullRequest(NamedTuple):
    number: int
    login: str
    sha: str
    url: str
    created_at: str = ''  # when it was opened: the first few on each lesson earn the early-PR bonus


class GitHub:
    """The production source. `api` fetches one GitHub REST path and returns the decoded JSON."""

    def __init__(self, api=None):
        self.api = api or self._fetch

    @staticmethod
    def _fetch(path):
        req = urllib.request.Request('https://api.github.com' + path, headers={'Accept': 'application/vnd.github+json'})
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
        if token:
            req.add_header('Authorization', 'Bearer ' + token)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    def pull_requests(self, repo):
        """Every submission: pull requests except the repo owner's, bots', and ones closed without merging."""
        owner, page, out = repo.split('/')[0].lower(), 1, []
        while True:
            batch = self.api(f'/repos/{repo}/pulls?state=all&per_page=100&page={page}')
            for pr in batch:
                withdrawn = pr['state'] == 'closed' and not pr.get('merged_at')
                if pr['user']['type'] == 'Bot' or pr['user']['login'].lower() == owner or withdrawn:
                    continue
                out.append(PullRequest(pr['number'], pr['user']['login'], pr['head']['sha'], pr['html_url'], pr.get('created_at') or ''))
            if len(batch) < 100:
                return out
            page += 1

    def display_name(self, login):
        return self.api(f'/users/{login}').get('name') or login

    def checkout(self, repo, number, dest):
        executor.fetch(f'https://github.com/{repo}.git', f'pull/{number}/head', dest)

    def fetch_repo(self, repo, dest, ref='HEAD'):
        """A repository at `ref` (default: its default branch), for a lesson's trial: the exercise's starter, or the
        solutions repository its tests came from."""
        executor.fetch(f'https://github.com/{repo}.git', ref, dest)


def grade_submission(lesson, source, pr, adapter=None):
    """Check out one pull request and run its lesson's check. Returns (passed, reasons): True or False for
    the participant's result, None when the grader itself failed (it is retried next run)."""
    with executor.workspace(adapter) as ws:
        try:
            source.checkout(lesson.repo, pr.number, ws.path)
            ws.share()
            return lesson.runner(ws, lesson)
        except checks.CheckFailed as e:
            return False, [str(e)]
        except Exception:
            return None, ['grader error, will retry:\n' + checks.tail(traceback.format_exc())]


def _verdict(passed, reasons):
    return f"  {({True: 'PASS', False: 'FAIL'}).get(passed, 'RETRY')}: " + submissions.first_lines(reasons, ' | ')


def grade_all(root, source=None, adapter=None, no_run=False, only=None, log=print, try_lesson=None):
    """Grade every new commit on every lesson's repository; record the results in grader/results.json. Then try
    each lesson still being checked (trial.run, or `try_lesson`), once per version of it.
    no_run: only record who submitted. only: grade just one pull request, e.g. "owner/repo#3" (no trials either).
    Returns the Submissions."""
    root = Path(root)
    source = source or GitHub()
    subs = submissions.Submissions(root)
    unreachable = set()  # logins whose profile could not be read this run
    for lesson in lessons.load(root):
        try:
            _ = lesson.runner  # load the check now: a broken module skips this lesson, not every lesson
        except Exception as e:
            log(f'Skipping {lesson.key} this run: cannot load its check "{lesson.check}" ({type(e).__name__}: {e})')
            continue
        try:
            prs = source.pull_requests(lesson.repo)
        except (urllib.error.URLError, OSError) as e:  # rate limit, outage, renamed repo: try again next run
            log(f'Skipping {lesson.repo} this run: cannot list pull requests ({e})')
            continue
        subs.keep_only(lesson, prs)  # a pull request closed without merging no longer counts
        for pr in prs:
            name = submissions.key(lesson, pr)
            if only and name != only:
                continue
            if pr.login not in subs.names and pr.login not in unreachable:  # never looked up, or the last try failed
                try:
                    subs.names[pr.login] = source.display_name(pr.login)
                except (urllib.error.URLError, OSError):
                    unreachable.add(pr.login)  # shown by login for now; asked again next run
            if no_run or not subs.needs_grading(lesson, pr):
                subs.record(lesson, pr)
                continue
            log(f'Grading {name} ({pr.login} @ {pr.sha[:7]})')
            passed, reasons = grade_submission(lesson, source, pr, adapter)
            log(_verdict(passed, reasons))
            subs.record_result(lesson, pr, passed, reasons)
            subs.save()  # keep progress if a later one hangs
    if not (no_run or only):
        for lesson in lessons.load(root, checking=True):
            if lesson.status != lessons.CHECKING:
                continue
            version = lessons.trial_version(lesson)
            if subs.needs_trial(lesson.key, version, trial.RETRY_FAILED_AFTER):
                log(f'Trying {lesson.key}, a lesson still being checked')
                passed, reasons = (try_lesson or trial.run)(lesson, source, adapter)
                log(_verdict(passed, reasons))
                subs.record_trial(lesson.key, version, passed, reasons)
                subs.save()
    subs.save()
    return subs
