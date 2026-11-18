"""Mutation testing: does a test fail when the code is subtly wrong?

    python3 grader/tests/mutate.py grader/roster.py              (its tests are found by name: test_roster)
    python3 grader/tests/mutate.py grader/submissions.py --tests test_submissions test_grading test_roster

For each place in the module where one small change would change behaviour (== for !=, < for <=, and for or,
a `not` dropped, + for -, a number off by one, True for False), it makes that one change in a throwaway copy of
the repository and runs the module's tests (the fast tier). A mutant the tests catch is "killed"; one they don't
"survives", and is printed: either a test is missing, or the change makes no difference (then mark the line
`# no mutate` and say why). Standard library only; nothing in this folder is changed.
"""
import argparse
import ast
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SWAPS = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.Gt: ast.LtE, ast.LtE: ast.Gt,
         ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
         ast.And: ast.Or, ast.Or: ast.And, ast.Add: ast.Sub, ast.Sub: ast.Add}
SKIP_DIRS = {'.git', '__pycache__', '.cache', 'node_modules', '.claude'}


class _Sites(ast.NodeVisitor):
    """Every mutation site, as (node path, description), in a stable order."""

    def __init__(self, skip_lines):
        self.sites, self.skip_lines = [], skip_lines

    def visit(self, node):
        if getattr(node, 'lineno', None) in self.skip_lines:
            return
        if isinstance(node, ast.Compare):
            self.sites += [(node, ('op', i)) for i, op in enumerate(node.ops) if type(op) in SWAPS]
        elif isinstance(node, ast.BoolOp) or (isinstance(node, ast.BinOp) and type(node.op) in SWAPS):
            self.sites.append((node, ('op', None)))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            self.sites.append((node, ('drop-not', None)))
        elif isinstance(node, ast.Constant) and isinstance(node.value, int):  # numbers, and True/False (bools are ints)
            self.sites.append((node, ('const', None)))
        self.generic_visit(node)


class _Mutate(ast.NodeTransformer):
    def __init__(self, target, how):
        self.target, self.how = target, how

    def visit(self, node):
        node = self.generic_visit(node)
        if node is not self.target:
            return node
        kind, i = self.how
        if kind == 'op' and isinstance(node, ast.Compare):
            node.ops[i] = SWAPS[type(node.ops[i])]()
        elif kind == 'op':
            node.op = SWAPS[type(node.op)]()
        elif kind == 'drop-not':
            return node.operand
        elif kind == 'const':
            node.value = (not node.value) if isinstance(node.value, bool) else node.value + 1
        return node


def mutants(source):
    """(line, original, mutated, new module source) for each mutation site."""
    skip = {n for n, line in enumerate(source.splitlines(), 1) if '# no mutate' in line}
    tree = ast.parse(source)
    sites = _Sites(skip)
    sites.visit(tree)
    for index in range(len(sites.sites)):
        tree = ast.parse(source)  # a fresh tree each time; find the same site again by position
        fresh = _Sites(skip)
        fresh.visit(tree)
        node, how = fresh.sites[index]
        before = ast.unparse(node)
        mutated = _Mutate(node, how).visit(tree)
        after = ast.unparse(node) if how[0] != 'drop-not' else ast.unparse(node.operand)
        yield node.lineno, before, after, ast.unparse(ast.fix_missing_locations(mutated))


def copy_repo(dest):
    def ignore(folder, names):
        return [n for n in names if n in SKIP_DIRS]
    shutil.copytree(REPO, dest, ignore=ignore, dirs_exist_ok=True)


def run_tests(root, tests, timeout):
    """'passed', 'failed' or 'timeout'."""
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')} | {'GRADER_FAST': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
    try:
        r = subprocess.run([sys.executable, '-m', 'unittest', '-q', *tests], cwd=root / 'grader' / 'tests', env=env,
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 'timeout'
    return 'passed' if r.returncode == 0 else 'failed'


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('module', help='e.g. grader/roster.py')
    p.add_argument('--tests', nargs='+', help='test modules to run (default: test_<module name>)')
    # Half the cores: copies run at once slow each other down, and a run slowed past its timeout is not a catch.
    p.add_argument('-j', '--jobs', type=int, default=max(1, (os.cpu_count() or 2) // 2))
    p.add_argument('--timeout', type=int, default=120, help='seconds per run, at least 5 times the unmutated run')
    a = p.parse_args(argv)
    module = Path(a.module).resolve().relative_to(REPO)
    tests = a.tests or [f'test_{module.stem}']
    original = (REPO / module).read_text(encoding='utf-8')
    found = list(mutants(original))
    # Mutants are written by ast.unparse, which drops comments and reformats; run the unmutated baseline the same
    # way, so only the mutation differs between a passing baseline and a mutant.
    source = ast.unparse(ast.parse(original))

    work = Path(tempfile.mkdtemp(prefix='mutate-'))
    try:
        roots = []
        for n in range(max(1, min(a.jobs, len(found)))):
            copy_repo(work / str(n))
            roots.append(work / str(n))
        (roots[0] / module).write_text(source, encoding='utf-8')
        began = time.monotonic()
        if run_tests(roots[0], tests, a.timeout * 10) != 'passed':
            raise SystemExit(f'The tests fail without any mutation: {" ".join(tests)}')
        timeout = max(a.timeout, 5 * (time.monotonic() - began))
        free = list(roots)

        def trial(m):
            root = free.pop()  # one copy per worker: the pool is as large as `roots`
            try:
                (root / module).write_text(m[3], encoding='utf-8')
                return m, run_tests(root, tests, timeout)
            finally:
                free.append(root)

        with ThreadPoolExecutor(len(roots)) as pool:
            results = list(pool.map(trial, found))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    survived = [m for m, r in results if r == 'passed']
    timed_out = [m for m, r in results if r == 'timeout']  # caught, but say so: a hang, or a machine too busy
    for word, found_ in (('SURVIVED', survived), ('TIMEOUT', timed_out)):
        for line, before, after, _ in found_:
            print(f'{word} {module}:{line}: {before}  ->  {after}')
    total = len(results)
    print(f'{module}: {total - len(survived)} of {total} mutants killed ({(total - len(survived)) * 100 // max(total, 1)}%)'
          + (f', {len(timed_out)} of them by timing out (over {timeout:.0f}s)' if timed_out else '') + f' by {" ".join(tests)}')
    return 1 if survived else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
