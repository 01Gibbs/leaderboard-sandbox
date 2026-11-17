"""Adding and removing a lesson the facilitator page's way: `leaderboard.py add-lesson` and `remove-lesson`, also as
rows of a facilitator batch.

A lesson added here is checked with one of the generic levels (none, build or tests), never a custom check, which
is code and so goes through a pull request. It is saved as "checking" (lessons.CHECKING): nothing grades it and
neither page shows it until a trial shows its tests work. Removing a lesson keeps its results and its
participants.csv column, so adding it again brings them back.
"""
import shutil
import tempfile
from pathlib import Path

import exercise_tests
import lessons
from submissions import Submissions
from checks.toolkit import CheckFailed, gradle_project
from exercise_tests import GENERIC, PinFailed

LEVELS = {'none': 'a facilitator marks it', 'build': 'correct when it builds'}


def add(root, key, label, repo, check, tests_repo='', tests_dir=''):
    """Add lesson `key`, as checking, with its tests pinned when `check` is tests. Returns what was done. Raises
    PinFailed, and changes nothing, when it cannot be added."""
    if check not in GENERIC:
        raise PinFailed(f'A lesson added here is checked with none, build or tests, not "{check}". '
                        'A custom check is added by a maintainer, through a pull request.')
    if (tests_repo or tests_dir) and check != 'tests':
        raise PinFailed(f'Where its tests come from only applies to a lesson checked with tests, not "{check}".')
    item = {'key': key, 'label': label, 'repo': repo, 'check': 'none' if check == 'tests' else check, 'status': lessons.CHECKING}
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
