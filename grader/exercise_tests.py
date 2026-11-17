"""Pin a lesson to the exercise repository's own tests (or another public repository's).

Most exercises ship the tests a participant has to make pass. `pin` copies them, as they are at one commit of
the exercise repository, into the lesson's test files (grader/fixtures/<key>/), and sets the lesson to the
`tests` level. Every submission is then graded with those copies, so a participant editing the tests does not
help, and a later change to the exercise repository regrades nobody until someone pins again.
"""
import os
import re
import shutil
import tempfile
from pathlib import Path

import executor
import lessons
import roster
from checks.toolkit import SKIP_DIRS, CheckFailed, gradle_project

GENERIC = ('none', 'build', 'tests')  # levels pinning may replace, and the only ones a lesson can be added with
# Pinning runs in the job that holds the deploy key, from a repository anyone could have written: plain files only,
# and not too many of them.
MAX_FILES, MAX_BYTES = 500, 5 * 1024 * 1024


def repo_url(repo):
    """Where to fetch a public repository from, without credentials."""
    return f'https://github.com/{repo}.git'


class PinFailed(roster.ActionError):
    """Pinning cannot be done, with a message saying why. Nothing has been changed."""


def pin(root, key, commit=None, url=None):
    """Copy the tests of lesson `key`'s repository at `commit` (a full commit id; default: its latest commit)
    into the leaderboard repository at `root` (grader/fixtures/<key>/) and record the commit in lessons.json.
    Returns (the commit pinned, how many test files). On failure nothing is changed."""
    if commit and not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise PinFailed('Give the full 40-character commit id, or leave it out to pin the latest commit.')
    try:
        lesson = next((l for l in lessons.load(root, checking=True) if l.key == key), None)
    except lessons.LessonsInvalid as e:
        raise PinFailed(str(e)) from None
    if lesson is None:
        raise PinFailed(f'No lesson "{key}" in lessons.json.')
    if lesson.check not in GENERIC:
        raise PinFailed(f'{key} uses the custom check "{lesson.check}", which pinning would replace. '
                        'Set its check to "none" in lessons.json first if that is what you want.')
    fixtures = lessons.fixtures(root)
    fixtures.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory(dir=fixtures, prefix='.pin-') as staged:
        source = lesson.tests_repo or lesson.repo
        sha = fetch(url or repo_url(source), commit or 'HEAD', Path(tmp))
        where = f'{source}{"/" + lesson.tests_dir if lesson.tests_dir else ""}'
        clone = Path(tmp).resolve()
        start = inside(clone, clone / lesson.tests_dir, where) if lesson.tests_dir else clone
        try:  # the folder grading copies the test files into
            project = inside(clone, gradle_project(start), where)
        except CheckFailed:
            raise PinFailed(f'{where} has no Gradle project at {sha[:7]}.') from None
        new = Path(staged) / key
        _copy_tests(clone, project, new, where)
        if not new.is_dir() or not any(f.is_file() for f in new.rglob('*')):
            raise PinFailed(f'{where} has no tests (src/test/) at {sha[:7]}.')
        _swap(new, fixtures / key, Path(staged) / 'old')
    lessons.record_pinned(root, key, sha)
    return sha, sum(1 for f in (fixtures / key).rglob('*') if f.is_file())


def inside(clone, path, where):
    """`path`, resolved, when it is in the fetched repository `clone`; a folder that is a symbolic link out of it
    (a tests folder, or one above it) would otherwise lead the copy anywhere on this machine."""
    resolved = Path(path).resolve()
    if resolved != clone and clone not in resolved.parents:
        raise PinFailed(f'{where}: {Path(path).relative_to(clone) if Path(path).is_relative_to(clone) else path} '
                        'leads outside the repository (a symbolic link); tests must be plain files in it.')
    return resolved


def _copy_tests(clone, project, dest, where):
    """Copy every src/test/ under `project` into `dest`, at the same paths: regular files only, from inside the
    fetched repository `clone`, within the caps."""
    count = size = 0
    for tests in (inside(clone, t, where) for t in _test_folders(project)):
        for dirpath, dirnames, filenames in os.walk(tests):
            for name in dirnames + filenames:
                path = Path(dirpath) / name
                if path.is_symlink():
                    raise PinFailed(f'{where}: {path.relative_to(project)} is a symbolic link; tests must be plain files.')
            for name in filenames:
                path = Path(dirpath) / name
                count, size = count + 1, size + path.stat().st_size
                if count > MAX_FILES:
                    raise PinFailed(f'{where} has more than {MAX_FILES} files under src/test/.')
                if size > MAX_BYTES:
                    raise PinFailed(f'{where} has more than {MAX_BYTES // (1024 * 1024)} MB under src/test/.')
                target = dest / path.relative_to(project)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)


def _test_folders(project):
    """Every src/test/ under the project, including those of subprojects such as app/."""
    for dirpath, dirnames, _ in os.walk(project):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        here = Path(dirpath)
        if here.name == 'test' and here.parent.name == 'src':
            dirnames[:] = []
            yield here


def _swap(new, dest, old):
    """Put `new` at `dest`; whatever was there is moved aside first and removed with the staging folder."""
    if dest.exists():
        dest.rename(old)
    new.rename(dest)


def fetch(url, ref, dest):
    """Check out `ref` of the repository at `url` into `dest` (see executor.fetch); PinFailed if it cannot."""
    try:
        return executor.fetch(url, ref, dest)
    except RuntimeError as e:
        raise PinFailed(f'Could not fetch {ref} from {url}: {e}') from None
