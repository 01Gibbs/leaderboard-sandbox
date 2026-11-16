"""Automated checks. A lesson's "check" in lessons.json names a module in this folder: checks/<name>.py, with a
function check(ws, lesson). Adding a module adds the check; names() finds it by its file name, without importing
it, and runner(name) imports it only when grading needs it. So lessons.json can be read, and facilitator
actions run, even while one check module is broken; grading skips that check's lessons. `build` and
`tests` are generic levels any lesson can use without writing Python; the others are custom checks for what
a generic level cannot do, such as calling the running app.

Each check is check(ws, lesson) -> (passed, reasons), or raises CheckFailed with a reason the participant can
act on. `ws` is an executor.Workspace holding the checked-out pull request at ws.path; participant code runs
only through ws.run and ws.start, except that the container check builds and runs the participant's image with
Docker (see executor.host_run; tests/test_boundaries.py keeps it to that check). A check never trusts the participant's own tests: it runs ours, or calls
the running application over HTTP.

A lesson's version (lessons.Lesson.version) covers its check's module and the SHARED modules, so editing one
check, constants included, regrades only the lessons that use it. For that to hold, a check imports only from
the SHARED modules, never from another check.
"""
import importlib
import pkgutil

SHARED = ['toolkit']  # modules here that every check is built from, rather than checks themselves
CHECKS = {}  # check functions loaded so far, by name. Tests add stand-ins here; that is the only other source.


def names():
    """Every check's name: one per module here, found by its file name (nothing is imported), and any in CHECKS."""
    return sorted({m.name for m in pkgutil.iter_modules(__path__) if m.name not in SHARED} | set(CHECKS))


def runner(name):
    """The check function called `name`, importing its module the first time; None for "none" or an unknown
    name. A module that cannot be imported raises its error here, for the grader to report."""
    if name not in CHECKS and name in names():
        CHECKS[name] = importlib.import_module(f'{__name__}.{name}').check
    return CHECKS.get(name)


def __getattr__(name):
    # What the grader and tests use from the toolkit, imported only when first asked for.
    if name in ('CheckFailed', 'jdks', 'tail'):
        from . import toolkit
        return getattr(toolkit, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
