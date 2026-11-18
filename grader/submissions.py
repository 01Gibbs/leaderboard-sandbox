"""Submissions: grader/results.json, one entry per pull request, and everything it means for scores.

grade.grade_all records here; Roster and the walkthrough read from here. What an entry means:
  - passed True: the check passed, so the lesson is correct;
  - passed False: the check failed, so the lesson is submitted;
  - passed None: not graded (a grader error, a lesson a facilitator marks by hand, or a --no-run), so the
    lesson is submitted, and an automated lesson is graded again next run;
  - a result counts until the pull request gets a new commit or its lesson changes (Lesson.version);
  - a pull request counts while GitHub lists it as a submission: one closed without merging is forgotten, and
    so loses its place among the first opened (the early-PR bonus). A status it already raised on the board
    stays, because the board never lowers one (Roster).
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from rules import EARLY_BONUS, RANK, to_int

UNCHECKED = 'no automated check for this lesson; a facilitator marks it'
LOGIN = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})')  # a GitHub username


class ResultsInvalid(ValueError):
    """results.json is not what the grader writes. Nothing is read from it."""


def _check(data):
    """Every problem with results.json's people and submissions, so a damaged or tampered file is refused before
    anything reaches participants.csv. Other top-level fields are kept as they are."""
    if not isinstance(data, dict):
        return ['it must be a JSON object']
    people, subs = data.get('people', {}), data.get('submissions', {})
    if not isinstance(people, dict) or not isinstance(subs, dict):
        return ['people and submissions must be objects']
    problems = [f'people: {l} must be a GitHub login with a text name' for l, n in people.items()
                if not (LOGIN.fullmatch(l) and isinstance(n, str))]
    for k, s in subs.items():
        if not isinstance(s, dict):
            problems.append(f'{k}: must be an object')
            continue
        if not (isinstance(s.get('login'), str) and LOGIN.fullmatch(s['login'])):
            problems.append(f'{k}: login must be a GitHub login')
        if not isinstance(s.get('task'), str):
            problems.append(f'{k}: task must be a lesson key')
        if s.get('passed') not in (True, False, None):
            problems.append(f'{k}: passed must be true, false or null')
    trials = data.get('trials', {})
    if not isinstance(trials, dict):
        return problems + ['trials must be an object']
    for k, t in trials.items():
        if not re.fullmatch(r'[a-z][a-z0-9_]*', k):
            problems.append(f'trials: {k} must be a lesson key')
        elif not (isinstance(t, dict) and t.get('passed') in (True, False, None) and isinstance(t.get('version'), str)
                and isinstance(t.get('at'), str) and isinstance(t.get('reasons'), list) and all(isinstance(r, str) for r in t['reasons'])):
            problems.append(f'trials: {k} must say passed (true, false or null), the version tried, when, and reasons')
    return problems


def when(stamp):
    return datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).timestamp()


def first_lines(reasons, sep):
    """Each reason's first line, joined: a one-line summary of a result or a trial."""
    return sep.join(r.splitlines()[0] for r in reasons if r)


def key(lesson, pr):
    """How a pull request is named in results.json and on the command line: "owner/repo#3"."""
    return f'{lesson.repo}#{pr.number}'


def _status(entry):
    return 'correct' if entry.get('passed') else 'submitted'


class Submissions:
    """grader/results.json of the leaderboard repository at `root`. A missing file is empty."""

    def __init__(self, root):
        self.file = Path(root) / 'grader' / 'results.json'
        self._load(self.file, 'grader/results.json')

    def _load(self, path, name):
        self._data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if problems := _check(self._data):
            raise ResultsInvalid(f'{name} has problems:\n  ' + '\n  '.join(problems))
        self._subs = self._data.setdefault('submissions', {})
        self.names = self._data.setdefault('people', {})  # GitHub login -> profile name

    def replace_with(self, path):
        """Take a grading run's results.json as this one, and save it. A file with problems is refused
        (ResultsInvalid) and nothing changes."""
        self._load(Path(path), "the grading run's results.json")
        self.save()

    def record_trial(self, key, version, passed, reasons, now=None):
        """Store lesson `key`'s trial (lesson_lifecycle decides when to run one and what it means). The section
        appears with the first trial, so a board without any is unchanged."""
        at = (now or datetime.now(timezone.utc)).strftime('%Y-%m-%dT%H:%M:%SZ')
        self._data.setdefault('trials', {})[key] = {'version': version, 'passed': passed, 'reasons': list(reasons), 'at': at}

    def forget_trial(self, key):
        """Forget lesson `key`'s trial (it was added again, or removed). Returns whether there was one."""
        return self._data.get('trials', {}).pop(key, None) is not None

    def trial(self, key):
        """The latest trial of lesson `key` ({version, passed, reasons}), or None."""
        return self._data.get('trials', {}).get(key)

    def save(self):
        text = json.dumps(self._data, sort_keys=True,
                          indent=2)  # no mutate: indent is layout
        self.file.write_text(text + '\n', encoding='utf-8')

    def name(self, login):
        """The person's GitHub profile name, or the login if it is not known."""
        return self.names.get(login) or login

    # ---------- grading ----------

    def _previous(self, lesson, pr):
        return self._subs.get(key(lesson, pr), {})

    def _still_valid(self, lesson, pr):
        previous = self._previous(lesson, pr)
        return (previous.get('passed') is not None and previous.get('sha') == pr.sha
                and previous.get('version') == lesson.version)

    def needs_grading(self, lesson, pr):
        """Whether this pull request's check should run: the lesson is automated and there is no result that
        still counts."""
        return lesson.runner is not None and not self._still_valid(lesson, pr)

    def record_result(self, lesson, pr, passed, reasons):
        """Record the outcome of running the lesson's check on this pull request, replacing any earlier one:
        passed True or False, or None when the grader itself failed (graded again next run)."""
        self._subs[key(lesson, pr)] = self._entry(lesson, pr) | {
            'passed': passed, 'reasons': reasons, 'version': lesson.version,
            'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}

    def record(self, lesson, pr):
        """Record a pull request without grading it: a result that still counts is kept (or, for the same
        commit, its pass or fail), with the pull request's latest details."""
        previous, entry = self._previous(lesson, pr), self._entry(lesson, pr)
        if self._still_valid(lesson, pr):
            entry = {**previous, **entry}
        elif lesson.runner is None:
            entry |= {'passed': None, 'reasons': [UNCHECKED]}
        else:
            same_commit = previous.get('sha') == pr.sha
            entry |= {'passed': previous.get('passed') if same_commit else None,
                      'reasons': previous.get('reasons', []) if same_commit else []}
        self._subs[key(lesson, pr)] = entry

    def keep_only(self, lesson, prs):
        """Forget the lesson's pull requests that are not in `prs`, every submission its repository has now."""
        listed = {key(lesson, pr) for pr in prs}
        for k in [k for k, s in self._subs.items() if s.get('task') == lesson.key and k not in listed]:
            del self._subs[k]

    @staticmethod
    def _entry(lesson, pr):
        return {'task': lesson.key, 'login': pr.login, 'url': pr.url, 'sha': pr.sha, 'check': lesson.check, 'created_at': pr.created_at}

    # ---------- reading ----------

    def best_statuses(self, lesson_keys):
        """[(login, lesson, status)]: each person's best status on each of `lesson_keys`, from all their pull
        requests. Logins differing only in case are one person. Sorted by lowercase login, then lesson."""
        best, spelling = {}, {}  # (login, lesson) -> status; lowercase login -> login as GitHub spells it
        for s in self._subs.values():
            if s['task'] not in lesson_keys:  # a lesson removed from lessons.json
                continue
            k = (s['login'].lower(), s['task'])
            spelling[k[0]] = s['login']
            if RANK[_status(s)] > RANK.get(best.get(k), -1):  # no mutate: any number below every rank
                best[k] = _status(s)
        return [(spelling[login], lesson, status) for (login, lesson), status in sorted(best.items())]

    def early_bonus(self, lesson_keys):
        """{lowercase login: points}: one point for each of the first pull requests opened on each lesson.
        Worked out from scratch every time, so it is never added up twice."""
        early = {}
        for lesson in lesson_keys:
            # Opened first = earliest created_at; results recorded before created_at existed fall back to PR number.
            opened = sorted((s for s in self._subs.values() if s['task'] == lesson),
                            key=lambda s: (s.get('created_at') or '', to_int(str(s.get('url', '')).rsplit('/', 1)[-1])))  # no mutate: [-1] is the same for any maxsplit
            for s in opened[:EARLY_BONUS['firstSubmissions']]:
                early[s['login'].lower()] = early.get(s['login'].lower(), 0) + 1
        return early

    def stats(self, lesson_key):
        """{submissions, people, correct} for one lesson: pull requests, distinct people, and passed ones."""
        subs = [s for s in self._subs.values() if s.get('task') == lesson_key]
        return {'submissions': len(subs), 'people': len({s.get('login') for s in subs}),
                'correct': sum(1 for s in subs if _status(s) == 'correct')}
