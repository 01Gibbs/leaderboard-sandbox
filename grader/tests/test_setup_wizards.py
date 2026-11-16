"""The setup wizards (grader/setup-leaderboard.sh), run against a stand-in for the GitHub CLI.

A wizard changes a real repository's settings, so here `gh` is a fake that records every call and answers as
GitHub would for a fresh repository or one already set up. The answers a person would type come on stdin.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
args, log = sys.argv[1:], os.environ['FAKE_GH_LOG']
stdin = '' if sys.stdin.isatty() else sys.stdin.read() if ('--input' in args or args[:2] == ['secret', 'set']) else ''
with open(log, 'a') as f:
    f.write(json.dumps({'args': args, 'stdin': stdin}) + '\n')
done = os.environ.get('FAKE_STATE') == 'done'
joined = ' '.join(args)
def say(text=''):
    print(text)
    sys.exit(0)
if args[:2] == ['auth', 'status']: say()
if args[:2] == ['repo', 'view']: say('o/board')
if args[:2] == ['secret', 'list']: say('LEADERBOARD_DEPLOY_KEY' if done else '')
if args[:2] == ['label', 'list']: say('facilitator' if done else '')
if args[0] == 'api':
    path = args[1]
    if path == 'repos/o/board' and '.permissions.admin' in joined: say('true')
    if path.endswith('/rulesets') and '-X' not in args: say('Protect main' if done else '')
    if path.endswith('/pages') and '-X' not in args:
        if done: say('workflow')
        sys.exit(1)  # 404: Pages is off
    if path.endswith('/collaborators') and '-X' not in args: say('owner')
    say('{}')
say()
'''


@unittest.skipUnless(shutil.which('bash') and shutil.which('ssh-keygen'), 'needs bash and ssh-keygen')
class SetupLeaderboardTests(unittest.TestCase):
    def run_wizard(self, answers, state='fresh'):
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work)
        bin_dir = work / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'gh').write_text(FAKE_GH)
        for name in ('gh', 'open', 'xdg-open', 'wslview'):
            path = bin_dir / name
            if name != 'gh':
                path.write_text('#!/bin/sh\nexit 0\n')  # never open a browser
            path.chmod(0o755)
        log = work / 'gh.log'
        env = {k: v for k, v in os.environ.items() if not k.startswith(('GH_', 'GITHUB_', 'LEADERBOARD_'))}
        env |= {'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'FAKE_GH_LOG': str(log), 'FAKE_STATE': state, 'ENV_FILE': str(work / '.env')}
        r = subprocess.run(['bash', str(REPO / 'grader' / 'setup-leaderboard.sh')], input='\n'.join(answers) + '\n',
                           cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return r, calls

    def find(self, calls, *words):
        return [c for c in calls if all(w in c['args'] for w in words)]

    # Banner, then per stage: the repository (y), deploy key (y), protect main (y), pages (y), settings (no question),
    # facilitators (names), first grading run (n), connect exercise repositories (n). Each stage ends with Enter.
    FRESH = ['', 'y', '', 'y', '', 'y', '', 'y', '', '', 'pat @sam', '', 'n', '', 'n']

    def test_a_fresh_repository_gets_every_setting(self):
        r, calls = self.run_wizard(self.FRESH)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        key = self.find(calls, 'deploy-key', 'add')
        self.assertEqual(len(key), 1)
        self.assertIn('--allow-write', key[0]['args'])
        self.assertFalse(Path(key[0]['args'][3]).exists(), 'the key files are deleted afterwards')
        secret = self.find(calls, 'secret', 'set', 'LEADERBOARD_DEPLOY_KEY')
        self.assertTrue(secret and secret[0]['stdin'].startswith('-----BEGIN OPENSSH PRIVATE KEY-----'))

        ruleset = json.loads(self.find(calls, 'repos/o/board/rulesets', 'POST')[0]['stdin'])
        self.assertEqual(ruleset['bypass_actors'], [{'actor_type': 'DeployKey', 'bypass_mode': 'always'}])
        rules = {rule['type']: rule.get('parameters') for rule in ruleset['rules']}
        self.assertEqual(rules['pull_request']['required_approving_review_count'], 0)
        self.assertEqual([c['context'] for c in rules['required_status_checks']['required_status_checks']], ['fast', 'slow'])
        self.assertIn('deletion', rules)
        self.assertIn('non_fast_forward', rules)

        self.assertTrue(self.find(calls, 'repos/o/board/pages', 'POST', 'build_type=workflow'))
        self.assertTrue(self.find(calls, 'repos/o/board/actions/permissions/workflow', 'default_workflow_permissions=read'))
        self.assertTrue(self.find(calls, 'repos/o/board/actions/permissions/fork-pr-contributor-approval',
                                  'approval_policy=all_external_contributors'))
        self.assertTrue(self.find(calls, 'label', 'create', 'facilitator'))
        invited = [c['args'][1] for c in calls if c['args'][:1] == ['api'] and '/collaborators/' in c['args'][1]]
        self.assertEqual(invited, ['repos/o/board/collaborators/pat', 'repos/o/board/collaborators/sam'])
        self.assertTrue(all('permission=push' in c['args'] for c in self.find(calls, 'PUT') if '/collaborators/' in c['args'][1]))
        self.assertFalse(self.find(calls, 'workflow', 'run'), 'the first grading run was declined')

    def test_running_it_again_changes_nothing_that_is_done(self):
        # Already done: no deploy key, ruleset or Pages question; settings re-applied (harmless); nobody invited.
        r, calls = self.run_wizard(['', 'y', '', '', '', '', '', '', '', '', 'n', '', 'n'], state='done')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.find(calls, 'deploy-key', 'add'))
        self.assertFalse(self.find(calls, 'secret', 'set'))
        self.assertFalse(self.find(calls, 'POST'))
        self.assertFalse(self.find(calls, 'label', 'create'))
        self.assertIn('already', r.stdout)

    def test_declining_everything_lists_what_is_left_to_do(self):
        r, calls = self.run_wizard(['', 'y', '', 'n', '', 'n', '', 'n', '', '', '', '', 'n', '', 'n'])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(self.find(calls, 'deploy-key', 'add'))
        for left in ('deploy key', 'Protect main', 'GitHub Pages', 'first grading run', 'setup-pr-trigger.sh'):
            self.assertIn(left, r.stdout)


class WizardShapeTests(unittest.TestCase):
    def test_both_wizards_share_the_same_library(self):
        marker = '# Sets up '
        libraries = [p.read_text().split(marker, 1)[0] for p in (REPO / 'grader').glob('setup-*.sh')]
        self.assertEqual(len(libraries), 2)
        self.assertEqual(libraries[0], libraries[1])

    def test_they_parse(self):
        for p in (REPO / 'grader').glob('setup-*.sh'):
            self.assertEqual(subprocess.run(['bash', '-n', str(p)]).returncode, 0, p.name)


if __name__ == '__main__':
    unittest.main()
