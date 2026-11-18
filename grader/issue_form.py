"""Facilitator changes sent as GitHub issues: what the facilitator page's Send opens, already filled in.

An issue made from one of .github/ISSUE_TEMPLATE/facilitator-*.yml says which form it is in its title
("Facilitator: Award points") and has one "### <label>" section per field. The changes-from-issues.yml workflow
runs this file with the issue's event, and only for issues from the owner, an organisation member or a collaborator
(anyone else's issue starts no run). It checks the author may change this repository (write, maintain or admin:
the same people who can run the Facilitator forms in the Actions tab; GitHub's Collaborators list decides) and
gives facilitator-action.yml the same command the Actions form would. Nothing from the issue reaches a shell.

FORMS, the templates and the facilitator-*.yml workflows must agree on titles, labels and
fields; grader/tests/test_issue_form.py fails if they don't.
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
# Each form: its title -> (leaderboard command, [(field label, workflow input)]), in the command's argument order.
FORMS = {
    'Award points': ('award', [('Person', 'person'), ('What for', 'kind'), ('Points (bonus only)', 'amount')]),
    'Mark an exercise': ('mark', [('Person', 'person'), ('Exercise', 'lesson'), ('Result', 'status')]),
    'Add a person': ('add', [('Full name', 'name'), ('GitHub username', 'github')]),
    'Rename a person': ('rename', [('Person', 'person'), ('Name to show', 'new_name')]),
    'Merge duplicate people': ('merge', [('Row to keep', 'keep'), ('Duplicate row', 'duplicate')]),
    'Undo the last change': ('undo', []),
}
DEFAULTS = {'amount': '1'}  # as facilitator-award.yml defaults it
# What the facilitator page sends: several changes in one issue (.github/ISSUE_TEMPLATE/facilitator-changes.yml),
# one per line, each a JSON list such as ["award", "Asha Rao", "helped", "1"]. It becomes `leaderboard.py batch`.
BATCH_TITLE = 'Changes'
BATCH_FIELDS = [('Batch', 'batch'), ('Changes', 'changes')]


class NotAForm(ValueError):
    """The issue is not one of the facilitator forms (or its title was changed)."""


def fields(body):
    """{label: value} from an issue form's body: each "### Label" section's text, "" for one left empty."""
    parts = re.split(r'^###[ \t]+(.+?)[ \t]*$', (body or '').replace('\r\n', '\n'), flags=re.M)
    found = {}
    for label, text in zip(parts[1::2], parts[2::2]):
        text = text.strip()
        found[label] = '' if text == NO_RESPONSE else text
    return found


def command(title, body):
    """The leaderboard command an issue asks for, as the Actions form would pass it: [command, *values]."""
    name = (title or '').removeprefix(TITLE_PREFIX).strip() if (title or '').startswith(TITLE_PREFIX) else None
    if name == BATCH_TITLE:
        return batch_command(body)
    form = FORMS.get(name)
    if form is None:
        raise NotAForm('This issue is not a facilitator form. Its title must start with one of: '
                       + ', '.join(TITLE_PREFIX + t for t in [*FORMS, BATCH_TITLE]) + '.')
    name, inputs = form
    given = fields(body)
    return [name, *(given.get(label, '') or DEFAULTS.get(field, '') for label, field in inputs)]


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
