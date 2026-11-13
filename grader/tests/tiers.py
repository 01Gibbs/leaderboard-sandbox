"""Which tests are slow: they build Java projects, run Docker, or simulate every workflow (minutes, not seconds).

GRADER_FAST=1 skips them: the pre-commit hook and the first CI job run only the fast tier, and a second CI job
runs the slow one. Without it, everything runs.
"""
import os
import unittest

slow = unittest.skipIf(os.environ.get('GRADER_FAST'), 'slow test; GRADER_FAST is set')
