"""Which tests are slow: they build Java projects, run Docker, or simulate every workflow (minutes, not seconds).

GRADER_FAST=1 skips them: the pre-commit hook and CI's `fast` job run only the fast tier. Without it, everything
runs, as in CI's `slow` job.
"""
import os
import unittest

slow = unittest.skipIf(os.environ.get('GRADER_FAST'), 'slow test; GRADER_FAST is set')
