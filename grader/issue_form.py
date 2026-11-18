"""Facilitator changes sent as a GitHub issue: the facilitator page's Send opens one "Facilitator: Changes" issue
(.github/ISSUE_TEMPLATE/facilitator-changes.yml) with every waiting change, which becomes `leaderboard.py batch`.

The changes-from-issues.yml workflow runs this file with the issue's event, and only for issues from the owner, an
organisation member or a collaborator (anyone else's issue starts no run). It checks the author may change this
repository (write, maintain or admin: the same people who can run the Facilitator forms in the Actions tab; GitHub's
Collaborators list decides) and gives facilitator-action.yml the command. Nothing from the issue reaches a shell.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import NamedTuple

TITLE_PREFIX = 'Facilitator: '
NO_RESPONSE = '_No response_'  # what GitHub writes for a field left empty
MAY_CHANGE = {'admin', 'maintain', 'write'}
# The issue's changes are one per line, each a JSON list such as ["award", "Asha Rao", "helped", "1"].
BATCH_TITLE = 'Changes'
BATCH_FIELDS = [('Batch', 'batch'), ('Changes', 'changes')]


class NotAForm(ValueError):
    """The issue is not the facilitator page's Changes issue (or its title was changed)."""


def fields(body):
    """{label: value} from an issue form's body: each "### Label" section's text, "" for one left empty."""
    parts = re.split(r'^###[ \t]+(.+?)[ \t]*$', (body or '').replace('\r\n', '\n'), flags=re.M)
    found = {}
    for label, text in zip(parts[1::2], parts[2::2]):
        text = text.strip()
        found[label] = '' if text == NO_RESPONSE else text
    return found


def command(title, body):
    """The leaderboard command the issue asks for: ["batch", id, rows]."""
    if (title or '').strip() != TITLE_PREFIX + BATCH_TITLE:
        raise NotAForm(f'This issue is not a facilitator form. Changes are sent from the facilitator page, as an issue '
                       f'titled "{TITLE_PREFIX}{BATCH_TITLE}"; one change at a time is a form in the Actions tab.')
    return batch_command(body)


def batch_body(batch, rows):
    """A Changes issue's body, as the facilitator page writes it (changes.js issueBody; a test holds them to the same
    text): the batch id, then one change a line, each a JSON list."""
    return f'### Batch\n\n{batch}\n\n### Changes\n\n' + '\n'.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in rows)


def batch_command(body):
    """["batch", id, JSON list of rows] from a Changes issue. A line that is not JSON is passed on as it is, for
    `leaderboard.py batch` to refuse with a reason."""
    given = fields(body)
    text = given.get('Changes', '')
    try:
        rows = json.dumps([json.loads(line) for line in text.splitlines() if line.strip()])
    except ValueError:
        rows = text
    return ['batch', given.get('Batch', ''), rows]


def permission(repo, login, token, api=None):
    """The author's permission on the repository (admin, write, read or none), as GitHub reports it."""
    def fetch(path):
        req = urllib.request.Request('https://api.github.com' + path, headers={
            'Accept': 'application/vnd.github+json', 'Authorization': 'Bearer ' + token, 'X-GitHub-Api-Version': '2022-11-28'})
        with urllib.request.urlopen(req, timeout=30) as r:  # no mutate: any sensible timeout
            return json.load(r)
    try:
        got = (api or fetch)(f'/repos/{repo}/collaborators/{login}/permission')
    except urllib.error.HTTPError as e:
        if e.code == 404:  # not a collaborator
            return 'none'
        raise
    return got.get('role_name') or got.get('permission') or 'none'


def decide(event, repo, token, api=None):
    """(allowed, args, reply): whether to make the change, the command if so, and what to answer if not."""
    issue = event['issue']
    login = issue['user']['login']
    try:
        args = command(issue.get('title'), issue.get('body'))
    except NotAForm as e:
        return False, None, f'Nothing was changed. {e}'
    role = permission(repo, login, token, api)
    if role not in MAY_CHANGE:
        return False, None, (f'Nothing was changed. Only the leaderboard\'s collaborators with write access can change it, '
                             f'and @{login} has {role} access. The repository owner can add you under Settings → Collaborators.')
    return True, args, ''


class Reply(NamedTuple):
    body: str  # the comment the issue gets
    close_reason: str  # 'completed' or 'not planned', as `gh issue close --reason` takes it
    lock_reason: str = 'resolved'  # then always locked, so it stays a record and draws no more notifications

    @property
    def state_reason(self):
        """The close reason as GitHub's API reports it on the issue ('completed' or 'not_planned')."""
        return self.close_reason.replace(' ', '_')


BROKE = 'Something went wrong before the change could be made. Nothing was changed: tell the repository owner.'


def answer(refusal, summary, outcome, run_url=''):
    """The issue's answer, from the read step's refusal (not allowed, or not a form), the change's summary and its
    outcome (changed, refused or broken, as leaderboard.py settled it; empty when nothing ran). Completed only when
    the change was made; always locked. The workflow and the practice copy both answer with this."""
    body = refusal or summary or BROKE
    if run_url:
        body += f'\n\n[The run that did this]({run_url})'
    return Reply(body, 'completed' if outcome == 'changed' else 'not planned')


def main_answer(body_file):
    """For changes-from-issues.yml: writes the comment to body_file, then prints the close reason and the lock
    reason, one per line."""
    env = os.environ
    reply = answer(env.get('REPLY', ''), env.get('SUMMARY', ''), env.get('OUTCOME', ''), env.get('RUN', ''))
    with open(body_file, 'w', encoding='utf-8') as f:
        f.write(reply.body)
    print(reply.close_reason)
    print(reply.lock_reason)
    return 0


def main():
    if sys.argv[1:2] == ['answer']:
        if len(sys.argv) != 3:
            sys.exit('usage: issue_form.py answer <file to write the comment to>')
        return main_answer(sys.argv[2])
    with open(os.environ['GITHUB_EVENT_PATH'], encoding='utf-8') as f:
        event = json.load(f)
    allowed, args, reply = decide(event, os.environ['GITHUB_REPOSITORY'], os.environ['GH_TOKEN'])
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
        out.write(f'allowed={"true" if allowed else "false"}\n')
        out.write(f'args={json.dumps(args) if args else ""}\n')  # JSON: one line, so it cannot add other outputs
        out.write(f'reply={" ".join(reply.split())}\n')  # one line, so it cannot add other outputs
    print(reply or f'Allowed: {args}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
