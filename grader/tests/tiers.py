"""Which tests are slow: they build Java projects, run Docker, or simulate every workflow (minutes, not seconds).

GRADER_FAST=1 skips them: the pre-commit hook and CI's `fast` job run only the fast tier. Without it, everything
runs, as in CI's `slow` jobs. CI splits the slow tier in two, side by side: the Gradle builds (GradleCheckTests,
about six minutes on their own) and the rest, which GRADER_SKIP_GRADLE=1 marks.
"""
import os
import unittest

slow = unittest.skipIf(os.environ.get('GRADER_FAST'), 'slow test; GRADER_FAST is set')
gradle_builds = unittest.skipIf(os.environ.get('GRADER_SKIP_GRADLE'), 'runs in CI\'s slow (gradle) job')
ON_CI = bool(os.environ.get('GITHUB_ACTIONS'))  # there, a missing tool fails a test instead of skipping it
