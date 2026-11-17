"""Leaderboard commands. Facilitators normally make these changes from the facilitator page, which sends them as
one GitHub issue (`batch`), or from the forms in the Actions tab (see FACILITATOR.md); this is the same thing from a
terminal. A person is named by their GitHub login or their name.

  add      "Name" [github-login]          put someone on the board who has not opened a pull request
  award    <person> stretch|helped|bonus [amount]   add points (a negative amount takes them away)
  mark     <person> <lesson> correct|submitted|none  set an exercise result by hand
  rename   <person> "New name"            show a real name instead of a GitHub login
  merge    <keep> <duplicate> [...]       combine rows for one person, keeping the higher value of each column
  undo     [change id]                    reverse the latest of the actions above, or one by its id (history lists ids)
  batch    <batch id> '<json list>'       several of the changes above, each recorded and undoable on its own
  history  [count]                        list recent actions
  grade    [--no-run] [--only owner/repo#N]   grade new pull requests (normally run by GitHub Actions)
  apply    [results.json]                 write graded results into participants.csv (from a grading run's file)
  pin-tests <lesson> [commit]             grade a lesson with its exercise repository's own tests, as they are at
                                          that full commit id (default: the latest), copied into grader/fixtures/<lesson>/
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roster  # noqa: E402  (grade and exercise_tests load the checks, so only their commands import them)
import submissions  # noqa: E402
from rules import COUNTS, STATUSES  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BATCHABLE = ('add', 'award', 'mark', 'rename', 'merge', 'undo')
REFUSED_HEADING = 'Nothing was changed.'  # what people read when a change is refused; machines read the outcome
CHANGES = BATCHABLE + ('batch',)  # the commands that change the leaderboard, so have an outcome
BATCH_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]{1,63}')


class BatchRefused(roster.ActionError):
    """Every row of a batch was refused. Nothing changed, but what happened to each row is saved, so this ends
    the run cleanly (exit 0) while still saying ❌."""


def parser(cls=argparse.ArgumentParser):
    p = cls(prog='leaderboard', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True, metavar='command')
    c = sub.add_parser('add', help='add a person')
    c.add_argument('name')
    c.add_argument('github', nargs='?', default='')
    c = sub.add_parser('award', help='add stretch, helped or bonus points')
    c.add_argument('person')
    c.add_argument('kind', choices=COUNTS)
    c.add_argument('amount', nargs='?', default='1')
    c = sub.add_parser('mark', help='set an exercise result by hand')
    c.add_argument('person')
    c.add_argument('lesson')
    c.add_argument('status', choices=STATUSES)
    c = sub.add_parser('rename', help='change the name shown')
    c.add_argument('person')
    c.add_argument('new_name')
    c = sub.add_parser('merge', help='combine duplicate rows')
    c.add_argument('keep')
    c.add_argument('duplicates', nargs='+')
    c = sub.add_parser('undo', help='reverse the latest action, or one by its id')
    c.add_argument('id', nargs='?', help='a change id from history, e.g. c12')
    c = sub.add_parser('history', help='list recent actions')
    c.add_argument('count', nargs='?', type=int, default=10)
    c = sub.add_parser('grade', help='grade new pull requests')
    c.add_argument('--no-run', action='store_true', help='record submissions without running checks')
    c.add_argument('--only', help='grade one pull request, e.g. AtulKumarSharma79/Frameworkupgrade#3')
    c = sub.add_parser('apply', help='write graded results into participants.csv')
    c.add_argument('results', nargs='?', help="a grading run's results.json to take first")
    c = sub.add_parser('batch', help='several changes at once, each recorded and undoable on its own')
    c.add_argument('id', help='names the batch, so the facilitator page can find what happened to each row')
    c.add_argument('rows', help='a JSON list of commands, each a list such as ["award", "Asha Rao", "helped", "1"]')
    c = sub.add_parser('pin-tests', help="grade a lesson with its exercise repository's own tests")
    c.add_argument('lesson')
    c.add_argument('commit', nargs='?')
    return p


def run(argv, root, board=None, parser_class=argparse.ArgumentParser):
    a = parser(parser_class).parse_args(argv)
    board = board or roster.Roster(root)
    if a.cmd == 'batch':
        return run_batch(board, a.id, a.rows, root)
    if a.cmd == 'add':
        return board.add(a.name, a.github)
    if a.cmd == 'award':
        return board.award(a.person, a.kind, a.amount)
    if a.cmd == 'mark':
        return board.mark(a.person, a.lesson, a.status)
    if a.cmd == 'rename':
        return board.rename(a.person, a.new_name)
    if a.cmd == 'merge':
        return board.merge(a.keep, a.duplicates)
    if a.cmd == 'undo':
        return board.undo(a.id)
    if a.cmd == 'history':
        return board.recent(a.count)
    if a.cmd == 'pin-tests':
        import exercise_tests
        sha, count = exercise_tests.pin(root, a.lesson, a.commit)
        return f'{a.lesson} is graded with its repository\'s {count} test files as of {sha[:7]}'
    if a.cmd == 'grade':
        import grade
        grade.grade_all(root, no_run=a.no_run, only=a.only)
        return None
    changes, warnings = board.apply_results(a.results)
    print('\n'.join([f'Warning: {w}' for w in warnings] + changes) or 'No changes')
    return None


class RowParser(argparse.ArgumentParser):
    """The command line's parser for one row of a batch: a mistake becomes that row's reason, and nothing (help,
    usage) is printed, so nothing from a row can reach the run's output or a commit title."""

    def error(self, message):
        raise roster.ActionError(message)

    def exit(self, status=0, message=None):
        raise roster.ActionError(message or 'that is not a change')

    def print_help(self, file=None):
        pass

    def print_usage(self, file=None):
        pass


def run_batch(board, batch_id, text, root):
    """Apply each row in order: a refused row does not stop the others. Every change made records its batch and
    row, and grader/batches.json records each row's outcome and change id (for undo), or why the whole batch was
    refused, so the facilitator page can show it either way."""
    if not BATCH_ID.fullmatch(batch_id):
        raise roster.ActionError(f'"{batch_id}" is not a batch id: 2 to 64 letters, digits and dashes.')
    if batch_id in board.batches():  # never overwrite what the page reads about the first time
        raise roster.ActionError(f'Batch {batch_id} was applied already.')
    try:
        rows = json.loads(text)
    except ValueError:
        rows = None
    if not (isinstance(rows, list) and rows and all(isinstance(r, list) and r for r in rows)):
        error = 'The batch is not a JSON list of changes, each a list such as ["award", "Asha Rao", "helped", "1"].'
    else:
        rows = [['' if v is None else str(v) for v in r] for r in rows]
        wrong = next((r[0] for r in rows if r[0] not in BATCHABLE), None)
        error = f'"{wrong}" cannot go in a batch. Only: {", ".join(BATCHABLE)}.' if wrong is not None else None
    if error:
        board.record_batch(batch_id, [], error=error)
        raise BatchRefused(f'the whole batch {batch_id} was refused.\n❌ {error}')
    outcomes = []
    for n, r in enumerate(rows, 1):
        board.batch, board.last_change = (batch_id, n), None
        try:
            message = run(r, root, board, RowParser)
            outcomes.append({'args': r, 'ok': True, 'message': message, 'change': board.last_change})
        except roster.ActionError as e:
            outcomes.append({'args': r, 'ok': False, 'message': str(e), 'change': None})  # ok says it was refused
        finally:
            board.batch = None
    board.record_batch(batch_id, outcomes)
    made = sum(o['ok'] for o in outcomes)
    lines = '\n'.join(('✅ ' if o['ok'] else '❌ ') + o['message'].splitlines()[0]
                      for o in outcomes)
    if not made:
        raise BatchRefused(f'0 of {len(rows)} changes made (batch {batch_id}).\n{lines}')
    return f'{made} of {len(rows)} changes made (batch {batch_id}).\n{lines}'


def main(argv, root=ROOT):
    try:
        # Workflows pass their form inputs as one JSON array, so no input is ever read by a shell.
        if argv[:1] == ['--args-json']:
            argv = ['' if v is None else str(v) for v in json.loads(argv[1])]  # a blank optional field arrives as null
        summary = run(argv, Path(root))
    except BatchRefused as e:
        report(f'{REFUSED_HEADING} {e}', failed=True)
        print(f'{REFUSED_HEADING} {str(e).splitlines()[0]}')  # the commit's title
        record('refused', e)
        return 0  # each row's outcome, or why the batch was refused, is saved: the workflow commits it
    except (roster.ActionError, submissions.ResultsInvalid) as e:  # exercise_tests.PinFailed is an ActionError
        report(f'{REFUSED_HEADING} {e}', failed=True)
        record('refused', e)
        return 1
    except BaseException as e:  # a fault, including arguments the workflow should never have sent (argparse exits)
        if not (isinstance(e, SystemExit) and e.code in (0, None)):
            record('broken')
        raise
    if argv[:1] and argv[0] in CHANGES:
        record('changed')
    if summary and argv[:1] == ['history']:
        print(summary)  # a listing, not a change: keep it off the run page's ✅ line
    elif summary:
        report(summary)
    return 0


def record(outcome, reason=''):
    """What happened, settled here once for whoever runs this: 'changed', 'refused' (an answer, with its reason on
    one line) or 'broken' (a fault). Written to the file LEADERBOARD_OUTCOME names, when it names one: the outcome
    on the first line, the reason on the second. read_outcome reads it back."""
    if not os.environ.get('LEADERBOARD_OUTCOME'):
        return
    reason = ' '.join(line.removeprefix('❌ ').strip() for line in str(reason).splitlines() if line.strip())
    try:
        Path(os.environ['LEADERBOARD_OUTCOME']).write_text(f'{outcome}\n{reason}')
    except OSError:  # never hide the fault being recorded
        pass


def read_outcome(path):
    """(outcome, reason) from a file record wrote. No file means the command never got as far: broken."""
    path = Path(path)
    if not path.is_file():
        return 'broken', ''
    outcome, _, reason = path.read_text().partition('\n')
    return outcome or 'broken', reason


def report(text, failed=False):
    print(text, file=sys.stderr if failed else sys.stdout)
    if os.environ.get('GITHUB_STEP_SUMMARY'):  # shows on the workflow run page
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
            f.write(('### ❌ ' if failed else '### ✅ ') + text.splitlines()[0] + '\n\n' + '\n'.join(text.splitlines()[1:]) + '\n')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
