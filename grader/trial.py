"""The trial of a lesson added from the facilitator page: does it work, before anyone is graded with it?

A lesson starts as "checking" (lessons.CHECKING). The grading job tries it, in the same sandboxed workspace as a
pull request, because a starter's Gradle build runs its code:
  - none: nothing to run; it passes;
  - build: the exercise's starter (its default branch) builds;
  - tests: the starter compiles with the pinned tests (failing them is expected: that is the exercise), and, when
    the tests came from another repository (a solutions repository), that project, at the commit the tests were
    pinned from, passes them.
A custom check is never tried here: it is code, and goes live through its pull request. Roster.apply_results then
puts a lesson whose trial passed live. A trial is tried again when anything it depends on changes
(lessons.trial_version), when the grader could not finish it, or a day after it failed (a starter fixed since, or a
network hiccup).
"""
import traceback

import checks
import executor
from checks.toolkit import CheckFailed, gradle, gradle_project, overlay

RETRY_FAILED_AFTER = 24 * 3600  # seconds


def run(lesson, source, adapter=None):
    """(passed, reasons): True or False, or None when the grader itself failed (it is tried again next run)."""
    if lesson.check == 'none':
        return True, ['a facilitator marks it: nothing to run']
    if lesson.check not in ('build', 'tests'):
        return False, [f'"{lesson.check}" is a custom check, which goes live through its pull request, not a trial']
    try:
        with executor.workspace(adapter) as ws:
            fetch(source, lesson.repo, ws.path)
            ws.share()
            project = gradle_project(ws.path)
            if lesson.check == 'build':
                gradle(ws, project, ['assemble'])
                return True, ['the starter builds']
            overlay(lesson.test_files, project)
            try:
                gradle(ws, project, ['compileTestJava'])
            except CheckFailed as e:
                raise CheckFailed(f'the pinned tests do not compile against the starter ({lesson.repo}):\n{e}') from None
        reasons = ['the pinned tests compile against the starter']
        if lesson.tests_repo and lesson.tests_repo.lower() != lesson.repo.lower():
            with executor.workspace(adapter) as ws:
                fetch(source, lesson.tests_repo, ws.path, lesson.tests_commit or 'HEAD')
                ws.share()
                project = gradle_project(ws.path / lesson.tests_dir if lesson.tests_dir else ws.path)
                overlay(lesson.test_files, project)
                try:
                    gradle(ws, project, ['test'])
                except CheckFailed as e:
                    raise CheckFailed(f'the solution in {lesson.tests_repo} does not pass the pinned tests:\n{e}') from None
            reasons.append(f'the solution in {lesson.tests_repo} passes them')
        return True, reasons
    except CheckFailed as e:
        return False, [str(e)]
    except Exception:
        return None, ['grader error, will try again:\n' + checks.tail(traceback.format_exc())]


def fetch(source, repo, dest, ref='HEAD'):
    """A repository the trial needs; one that cannot be fetched fails the trial, saying why."""
    try:
        source.starter(repo, dest, ref)
    except RuntimeError as e:
        raise CheckFailed(f'could not fetch {repo}: is it public? ({str(e).strip().splitlines()[-1] if str(e).strip() else e})') from None
