"""Rules about where code may start processes, checked by reading the source.

Participant code must run only through executor.Workspace (ws.run / ws.start), as the sandbox user in CI.
These tests fail when new code starts a process some other way, so the rule cannot drift silently.
"""
import ast
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCES = sorted(p for p in [*(REPO / 'grader').rglob('*.py'), REPO / 'walkthrough.py'] if 'tests' not in p.parts)

# Modules that may import subprocess, and why. Everything else starts processes through executor.
SUBPROCESS_ALLOWED = {
    'grader/executor.py': 'the one place participant code runs',
    'grader/roster.py': 'git config user.name, to say who made a local change',
    'walkthrough.py': 'git remote get-url, for the GitHub links',
}
# host_run runs trusted tools with a clean environment, never as the sandbox user: which tool, from where.
HOST_RUN_ALLOWED = {
    'git': {'grader/executor.py'},  # executor.fetch: checking out pull requests and exercise repositories
    # docker builds and runs the participant's image: their code runs in containers on the host's Docker daemon,
    # not as the sandbox user. Only the container check may do this.
    'docker': {'grader/checks/container_image.py', 'grader/checks/toolkit.py'},
}


def parsed():
    for path in SOURCES:
        yield path.relative_to(REPO).as_posix(), ast.parse(path.read_text(encoding='utf-8'))


class ProcessBoundaryTests(unittest.TestCase):
    def test_only_the_allowed_modules_import_subprocess(self):
        for name, tree in parsed():
            imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            imported |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            if 'subprocess' in imported:
                self.assertIn(name, SUBPROCESS_ALLOWED, f'{name} imports subprocess; start processes through executor')

    def test_no_shell_or_exec_calls(self):
        for name, tree in parsed():
            for n in ast.walk(tree):
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == 'os':
                    self.assertFalse(n.attr == 'system' or n.attr.startswith(('exec', 'spawn', 'popen')),
                                     f'{name}:{n.lineno} uses os.{n.attr}')

    def test_host_run_runs_only_git_and_docker_from_the_allowed_places(self):
        for name, tree in parsed():
            for n in ast.walk(tree):
                func = getattr(n, 'func', None)
                called = getattr(func, 'attr', None) or getattr(func, 'id', None)
                if not (isinstance(n, ast.Call) and called == 'host_run'):
                    continue
                cmd = n.args[0] if n.args else None
                tool = cmd.elts[0].value if isinstance(cmd, ast.List) and cmd.elts and isinstance(cmd.elts[0], ast.Constant) else None
                self.assertIn(name, HOST_RUN_ALLOWED.get(tool, set()), f'{name}:{n.lineno} runs {tool or "a computed command"} with host_run')

    def test_checks_import_only_from_the_toolkit(self):
        # A lesson's version covers its own check module, the toolkit and executor, so a check that imported
        # anything else from the grader could change without regrading its lessons.
        grader_modules = {p.stem for p in (REPO / 'grader').glob('*.py')}
        for path in (REPO / 'grader' / 'checks').glob('*.py'):
            if path.name == 'toolkit.py':
                continue
            for n in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                    self.assertNotIn(n.module.split('.')[0], grader_modules, f'checks/{path.name} imports {n.module}; use .toolkit')


if __name__ == '__main__':
    unittest.main()
