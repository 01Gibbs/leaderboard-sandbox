"""A lesson's life, from the facilitator page to live: the one place that decides it.

  add       `leaderboard.py add-lesson` (also a row of a facilitator batch): saved as "checking" (lessons.CHECKING),
            with its tests pinned for the tests level. Nothing grades it and neither page shows it yet.
  try_due   grading: each lesson being checked whose trial is due is tried, through `run_trial` (the seam:
            trial.run on GitHub, a pretend trial in practice). Due means never tried at this version, not
            finished last time, or failed more than a day ago.
  promote_passed   applying results: a lesson being checked goes live when its trial passed for `version`, the
            lesson as it is now: its check and pinned tests, where its code and tests come from, when it was added,
            and trial.py. A lesson added again is a new version, so an old trial never puts it live.
  remove    `leaderboard.py remove-lesson`: its results and participants.csv column stay, so adding it again
            brings them back.

Its status lives in lessons.json and its trial in grader/results.json; only this module reads both together.
A lesson added here is checked with one of the generic levels (none, build or tests), never a custom check, which
is code and so goes through a pull request.
"""
import hashlib
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import lessons
from submissions import Submissions, first_lines, when

LEVELS = {'none': 'a facilitator marks it', 'build': 'correct when it builds'}
RETRY_FAILED_AFTER = 24 * 3600  # seconds: a starter fixed since, or a network hiccup


def version(lesson):
    """What a lesson's trial depends on (see the module's notes). A trial of another version does not count.
    Hashes trial.py's text rather than importing it, so putting a lesson live needs none of the grading code."""
    h = hashlib.sha256('\n'.join([lesson.version, lesson.repo, lesson.tests_repo, lesson.tests_dir, lesson.tests_commit, lesson.added]).encode())
    h.update((lessons.HERE / 'trial.py').read_bytes())
    return h.hexdigest()[:12]  # no mutate: any length that is unlikely to collide


def _checking(root):
    return [lesson for lesson in lessons.load(root, checking=True) if lesson.status == lessons.CHECKING]


def _due(trial, current, now):
    if not trial or trial['version'] != current or trial['passed'] is None:
        return True
    return trial['passed'] is False and now.timestamp() - when(trial['at']) > RETRY_FAILED_AFTER


def try_due(root, subs, run_trial, now=None, log=print):
    """Try each lesson being checked whose trial is due: `run_trial(lesson)` returns (passed, reasons), passed True,
    False, or None when the grader could not finish. Each trial is recorded in `subs` and saved straight away, so a
    later one that hangs loses nothing. Returns the keys tried."""
    now = now or datetime.now(timezone.utc)
    tried = []
    for lesson in _checking(root):
        current = version(lesson)
        if not _due(subs.trial(lesson.key), current, now):
            continue
        log(f'Trying {lesson.key}, a lesson still being checked')
        passed, reasons = run_trial(lesson)
        log(f"  {({True: 'PASS', False: 'FAIL'}).get(passed, 'RETRY')}: " + first_lines(reasons, ' | '))
        subs.record_trial(lesson.key, current, passed, reasons, now=now)
        subs.save()
        tried.append(lesson.key)
    return tried


def promote_passed(root, subs):
    """Put live each lesson being checked whose trial (in `subs`) passed for the lesson as it is now. Returns a
    line for each, saying why."""
    live = []
    for lesson in _checking(root):
        t = subs.trial(lesson.key)
        if t and t['passed'] is True and t['version'] == version(lesson):
            lessons.promote(root, lesson.key)
            live.append(f'{lesson.label} is live: ' + first_lines(t['reasons'], '; '))
    return live


def add(root, key, label, repo, check, tests_repo='', tests_dir=''):
    """Add lesson `key`, as checking, with its tests pinned when `check` is tests. Returns what was done. Raises
    PinFailed, and changes nothing, when it cannot be added."""
    import exercise_tests  # pinning (and the check toolkit) loads only for adding and removing: never for grading's
    from checks.toolkit import CheckFailed, gradle_project  # trials or putting lessons live, nor people's changes
    from exercise_tests import GENERIC, PinFailed
    if check not in GENERIC:
        raise PinFailed(f'A lesson added here is checked with none, build or tests, not "{check}". '
                        'A custom check is added by a maintainer, through a pull request.')
    if (tests_repo or tests_dir) and check != 'tests':
        raise PinFailed(f'Where its tests come from only applies to a lesson checked with tests, not "{check}".')
    item = {'key': key, 'label': label, 'repo': repo, 'check': 'none' if check == 'tests' else check, 'status': lessons.CHECKING,
            'added': datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')}  # each add a new trial
    item.update({k: v for k, v in (('tests_repo', tests_repo), ('tests_dir', tests_dir)) if v})
    problems = lessons.problems_adding(root, item)  # before anything is fetched
    if problems:
        raise PinFailed('; '.join(p.split(': ', 1)[-1] for p in problems))
    with tempfile.TemporaryDirectory() as tmp:  # public: fetched with no credentials
        sha = exercise_tests.fetch(exercise_tests.repo_url(repo), 'HEAD', Path(tmp))
        if check == 'build':
            try:
                gradle_project(tmp)
            except CheckFailed:
                raise PinFailed(f'{repo} has no Gradle project at {sha[:7]}, so "build" cannot check it.') from None
    lessons.add(root, item)
    forget_trial(root, key)  # a lesson added again is tried again, whatever it was before
    if check != 'tests':
        return f'Added {label} ({LEVELS[check]}), checking until its trial passes.'
    try:
        pinned, count = exercise_tests.pin(root, key)
    except PinFailed:
        lessons.remove(root, key)
        raise
    return f'Added {label} (tests: {count} files from {tests_repo or repo} at {pinned[:7]}), checking until its trial passes.'


def forget_trial(root, key):
    subs = Submissions(root)
    if subs.forget_trial(key):
        subs.save()


def remove(root, key):
    """Remove lesson `key` and its pinned tests. Its graded results and its participants.csv column stay (nothing
    shows them), so adding it again brings them back. A lesson with a custom check is removed through a pull
    request: its check and reference files are code."""
    from exercise_tests import GENERIC, PinFailed
    try:
        lesson = next((lesson for lesson in lessons.load(root, checking=True) if lesson.key == key), None)
    except lessons.LessonsInvalid as e:
        raise PinFailed(str(e)) from None
    if lesson is None:
        raise PinFailed(f'No lesson "{key}" in lessons.json.')
    if lesson.check not in GENERIC:
        raise PinFailed(f'{lesson.label} has the custom check "{lesson.check}": a maintainer removes it through a pull request.')
    lessons.remove(root, key)
    shutil.rmtree(lessons.fixtures(root) / key, ignore_errors=True)
    forget_trial(root, key)
    return f'Removed {lesson.label}. Its results are kept: adding it again brings them back.'
