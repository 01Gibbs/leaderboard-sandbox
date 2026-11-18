"""Lessons: the exercises on the leaderboard, as listed in lessons.json.

Everything else (the grader, the roster, the walkthrough) reads lessons through `load(root)`, so a mistake in
lessons.json is reported the same way everywhere, with every problem listed at once. This module also owns where
lessons.json and each lesson's test files live in a leaderboard repository, and every write to lessons.json
(`record_pinned`, `add`, `remove`, and `promote`, which puts a lesson whose trial passed live).

A lesson added from the facilitator page starts as "checking" (status), until a trial shows its tests work. Only
`load(root, checking=True)` returns those: grading, the roster and the pages never see them.
"""
import hashlib
import inspect
import json
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import checks
import rules

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # this leaderboard repository
# participants.csv columns that are not lessons, and header spellings read as one of them
RESERVED = tuple(rules.BASE_COLUMNS + rules.COUNTS + rules.GENERATED + list(rules.RULES['headerAliases']))
FIELDS = ('key', 'label', 'repo', 'check', 'tests_commit', 'tests_repo', 'tests_dir', 'status')  # what a lesson may have
CHECKING = 'checking'  # status of a lesson not yet shown or graded
# Used by every check, so a change to any of these regrades every automated lesson.
SHARED_CODE = [HERE / 'executor.py'] + [HERE / 'checks' / f'{m}.py' for m in checks.SHARED]


class LessonsInvalid(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__('lessons.json has problems:\n  ' + '\n  '.join(problems))


@dataclass(frozen=True)  # no mutate: frozen guards against accidents; nothing relies on it
class Lesson:
    key: str          # the participants.csv column
    label: str        # shown on the page
    repo: str         # owner/name: where participants open pull requests
    check: str        # how "correct" is decided: 'none' or a name in checks.names() (a module in grader/checks/)
    test_files: Path  # our files for this lesson: tests copied over each submission, or a check's reference files
    tests_repo: str = ''  # owner/name its tests are pinned from, when not `repo`
    tests_dir: str = ''   # the folder in that repository holding the project whose src/test/ is pinned
    status: str = ''      # CHECKING until its trial passes; empty once live
    tests_commit: str = ''  # the commit its tests were pinned from

    @property
    def runner(self):
        """The check function, or None when a facilitator marks the lesson by hand. Imports the check's module
        the first time, so only grading needs it (and raises if that module is broken)."""
        return checks.runner(self.check)

    @cached_property
    def version(self):
        """Changes whenever anything that decides this lesson's results changes: its check name, its check's
        module (grader/checks/<check>.py, constants included), the code every check shares (SHARED_CODE), or
        its test files. Other checks' modules are left out, so editing one check regrades only its lessons.
        Results graded under another version are graded again."""
        h = hashlib.sha256(self.check.encode())
        if self.runner:
            h.update(Path(inspect.getsourcefile(self.runner)).read_bytes())
            for f in SHARED_CODE:
                h.update(Path(f).read_bytes())
        if self.test_files.is_dir():
            for f in sorted(self.test_files.rglob('*')):
                if f.is_file():
                    h.update(f.relative_to(self.test_files).as_posix().encode() + f.read_bytes())
        return h.hexdigest()[:12]  # no mutate: any length that is unlikely to collide


def trial_version(lesson):
    """What the trial of a checking lesson (grader/trial.py) depends on: the lesson itself (its check and pinned
    tests), where its code and tests come from, and trial.py. A trial of another version does not count. Read here,
    not in trial.py, so putting a lesson live needs none of the grading code loaded."""
    h = hashlib.sha256('\n'.join([lesson.version, lesson.repo, lesson.tests_repo, lesson.tests_dir, lesson.tests_commit]).encode())
    h.update((HERE / 'trial.py').read_bytes())
    return h.hexdigest()[:12]  # no mutate: any length that is unlikely to collide


def lessons_file(root=ROOT):
    return Path(root) / 'lessons.json'


def fixtures(root=ROOT):
    """grader/fixtures: one folder of test files per lesson."""
    return Path(root) / 'grader' / 'fixtures'


FIXTURES = fixtures()


def load(root=ROOT, checking=False):
    """The lessons of the leaderboard repository at `root`, in order: the live ones, and with checking=True those
    still being checked too. Raises LessonsInvalid listing every problem (of every lesson, checking or not)."""
    try:
        items = json.loads(lessons_file(root).read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise LessonsInvalid([f'cannot read it as JSON ({e})']) from None
    out, problems = _check(items, root, checking)
    if problems:
        raise LessonsInvalid(problems)
    return out


def _check(items, root, checking):
    """(the lessons, every problem) for lessons.json's list `items`."""
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        return [], ['it must be a list of lessons, each one {"key": ..., "label": ..., "repo": ..., "check": ...}']
    problems, seen, repos, out = [], set(), {}, []
    for n, item in enumerate(items, 1):
        where = f'lesson {n}' + (f' ({item["key"]})' if isinstance(item.get('key'), str) and item['key'] else '')
        problems += [f'{where}: unknown field "{f}"; the fields are {", ".join(FIELDS)}' for f in item if f not in FIELDS]
        bad = [f for f in FIELDS if f in item and not isinstance(item[f], str)]
        problems += [f'{where}: {f} must be text' for f in bad]
        item = {f: v for f, v in item.items() if f in FIELDS and f not in bad}
        key, check = item.get('key', ''), item.get('check', 'none')
        if not re.fullmatch(r'[a-z][a-z0-9_]*', key):
            problems.append(f'{where}: key "{key}" must be lowercase letters, digits and _')
        elif key in seen or key in RESERVED:
            problems.append(f'{where}: key "{key}" is already used')
        seen.add(key)
        if not item.get('label'):
            problems.append(f'{where}: needs a label')
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', item.get('repo', '')):
            problems.append(f'{where}: repo must look like owner/name')
        elif item['repo'].lower() in repos:  # their pull requests would be one lesson's results
            problems.append(f'{where}: {item["repo"]} is already the repository of {repos[item["repo"].lower()]}: one lesson per repository')
        repos.setdefault(item.get('repo', '').lower(), item.get('label') or key)
        if check != 'none' and check not in checks.names():
            problems.append(f'{where}: check must be one of none, {", ".join(checks.names())}')
        if 'tests_commit' in item and not (check == 'tests' and re.fullmatch(r'[0-9a-f]{40}', str(item['tests_commit']))):
            problems.append(f'{where}: tests_commit must be a full commit id, on a lesson whose check is tests')
        if 'tests_repo' in item and not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', item['tests_repo']):
            problems.append(f'{where}: tests_repo must look like owner/name')
        folder = item.get('tests_dir', '')
        if 'tests_dir' in item and (not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*(/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*', folder)):
            problems.append(f'{where}: tests_dir must be a folder in that repository, such as greeting or app/greeting')
        if item.get('status', CHECKING) != CHECKING:
            problems.append(f'{where}: status can only be "{CHECKING}" (leave it out once the lesson is live)')
        lesson = Lesson(key, item.get('label', ''), item.get('repo', ''), check, fixtures(root) / key,
                        item.get('tests_repo', ''), item.get('tests_dir', ''), item.get('status', ''), item.get('tests_commit', ''))
        if checking or lesson.status != CHECKING:
            out.append(lesson)
    return out, problems


def _write(root, items):
    text = json.dumps(items, ensure_ascii=False, indent=2)  # no mutate: indent is layout (lessons.json is written with 2)
    lessons_file(root).write_text(text + '\n', encoding='utf-8')


def problems_adding(root, item):
    """What would be wrong with lessons.json after appending lesson `item` (a dict of FIELDS): [] when nothing."""
    items = json.loads(lessons_file(root).read_text(encoding='utf-8'))
    return _check(items + [item], root, True)[1] if isinstance(items, list) else ['lessons.json is not a list']


def add(root, item):
    """Append lesson `item`. Raises LessonsInvalid, and writes nothing, when the result would have problems."""
    problems = problems_adding(root, item)
    if problems:
        raise LessonsInvalid(problems)
    _write(root, json.loads(lessons_file(root).read_text(encoding='utf-8')) + [item])


def promote(root, key):
    """Put lesson `key` live: it is shown and graded from now on."""
    items = json.loads(lessons_file(root).read_text(encoding='utf-8'))
    for item in items:
        if item.get('key') == key:
            item.pop('status', None)
    _write(root, items)


def remove(root, key):
    """Remove lesson `key` from lessons.json. Its test files are the caller's to remove."""
    _write(root, [i for i in json.loads(lessons_file(root).read_text(encoding='utf-8')) if i.get('key') != key])


def record_pinned(root, key, commit):
    """Grade lesson `key` with its pinned test files from now on: check "tests", tests_commit `commit`.
    Every other lesson is left as it is."""
    path = lessons_file(root)
    items = json.loads(path.read_text(encoding='utf-8'))
    item = next(i for i in items if i.get('key') == key)
    item['check'], item['tests_commit'] = 'tests', commit
    _write(root, items)
