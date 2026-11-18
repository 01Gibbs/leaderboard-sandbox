"""changes.js: the facilitator page's Changes box, without the page. What waits, what is sent and how (the issue
GitHub is opened with), and what became of each row once grader/batches.json says, or once it has been too long.

Run in Node.js with a stand-in clock, so a test says when things happen and what batches.json holds.
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'grader'))
import issue_form  # noqa: E402

CHANGES_JS = REPO / 'changes.js'

# The scenario is a JS function body given (box, clock, log, issueBody); `clock.t` is the time now.
_RUN = r'''
const fs = require('fs'), vm = require('vm');
const { scenario, options } = JSON.parse(fs.readFileSync(0, 'utf8'));
const clock = { t: 1_000_000 };
let n = 0;
const ctx = { URLSearchParams }; vm.createContext(ctx);  // as a browser gives it
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const box = vm.runInContext('changesBox', ctx)({ repo: 'o/board', giveUp: 600000, now: () => clock.t, newBatchId: () => 'b' + (++n), ...options });
const log = [];
new Function('box', 'clock', 'log', 'issueBody', scenario)(box, clock, log, vm.runInContext('issueBody', ctx));
process.stdout.write(JSON.stringify({ log, rows: box.rows() }));
'''


def run(scenario, **options):
    r = subprocess.run(['node', '-e', _RUN, str(CHANGES_JS)], capture_output=True, text=True, timeout=60,
                       input=json.dumps({'scenario': scenario, 'options': options}))
    if r.returncode:
        raise AssertionError('changes.js failed in Node:\n' + r.stderr)
    return json.loads(r.stdout)


AWARD = "['award', 'Asha Rao', 'helped', '1']"
MARK = "['mark', 'Ben Okafor', 'fizzbuzz', 'correct']"


@unittest.skipUnless(shutil.which('node'), 'needs Node.js to run changes.js')
class WaitingTests(unittest.TestCase):
    def test_a_change_waits_until_sent_and_the_same_one_is_not_added_twice(self):
        out = run(f"log.push(box.add({AWARD}, 'Give 1 help.')); log.push(box.add({AWARD}, 'Give 1 help.'));")
        self.assertEqual(out['log'], [None, {'say': 'Already in Changes.'}])
        self.assertEqual([(r['state'], r['text']) for r in out['rows']], [('queued', 'Give 1 help.')])

    def test_the_same_change_may_be_added_again_once_the_first_is_done_or_failed(self):
        out = run(f"box.add({AWARD}, 'x'); box.send(); box.settle({{ b1: {{ rows: [{{ ok: true, change: 'c1' }}] }} }});"
                  f"log.push(box.add({AWARD}, 'x'));")
        self.assertEqual(out['log'], [None])
        self.assertEqual([r['state'] for r in out['rows']], ['done', 'queued'])

    def test_at_most_40_wait_at_once(self):
        out = run("for (let i = 0; i < 41; i++) log.push(box.add(['award', 'P' + i, 'helped', '1'], 'x'));")
        self.assertEqual(out['log'][-1], {'error': 'Send these 40 first.'})
        self.assertEqual(len(out['rows']), 40)

    def test_remove_and_retry_and_clear_done(self):
        out = run(f"box.add({AWARD}, 'a'); box.add({MARK}, 'm'); box.remove(box.rows()[0].key);"
                  "box.send(); box.settle({ b1: { rows: [{ ok: false, message: 'No such person' }] } });"
                  "log.push(box.rows().map((r) => r.state)); box.retry(box.rows()[0].key);")
        self.assertEqual(out['log'], [['failed']])
        self.assertEqual([(r['args'][0], r['state']) for r in out['rows']], [('mark', 'queued')])
        out = run(f"box.add({AWARD}, 'a'); box.send(); box.settle({{ b1: {{ rows: [{{ ok: true }}] }} }}); box.clearDone();")
        self.assertEqual(out['rows'], [])

    def test_pending_finds_what_waits_or_is_sent(self):
        out = run(f"box.add({AWARD}, 'a'); box.add({MARK}, 'm'); box.send();"
                  "log.push(box.pending((a) => a[0] === 'mark'), box.pending((a) => a[0] === 'undo'));")
        self.assertEqual(out['log'], [True, False])


@unittest.skipUnless(shutil.which('node'), 'needs Node.js to run changes.js')
class SendTests(unittest.TestCase):
    def test_send_opens_one_issue_with_every_waiting_row_numbered(self):
        out = run(f"box.add({AWARD}, 'a'); box.add({MARK}, 'm'); log.push(box.send()); log.push(box.send());")
        sent, again = out['log']
        self.assertIsNone(again, 'nothing left to send')
        self.assertEqual((sent['batch'], sent['count'], sent['left'], sent['title']), ('b1', 2, 0, 'Facilitator: Changes'))
        self.assertEqual(sent['body'], '### Batch\n\nb1\n\n### Changes\n\n["award","Asha Rao","helped","1"]\n["mark","Ben Okafor","fizzbuzz","correct"]')
        self.assertTrue(sent['url'].startswith('https://github.com/o/board/issues/new?template=facilitator-changes.yml&'))
        self.assertEqual([(r['state'], r['batch'], r['row'], r['sentAt']) for r in out['rows']], [('waiting', 'b1', 1, 1000000), ('waiting', 'b1', 2, 1000000)])

    def test_what_does_not_fit_in_the_address_waits_for_the_next_send(self):
        out = run("for (let i = 0; i < 30; i++) box.add(['rename', 'Person ' + i, 'A rather long new name ' + 'x'.repeat(200)], 'r');"
                  "log.push(box.send());", maxUrl=3000)
        sent = out['log'][0]
        self.assertLessEqual(len(sent['url']), 3000)
        self.assertEqual(sent['count'] + sent['left'], 30)
        self.assertGreater(sent['left'], 0)
        self.assertEqual(sum(r['state'] == 'queued' for r in out['rows']), sent['left'])

    def test_one_row_too_long_is_still_sent(self):
        out = run("box.add(['rename', 'P', 'y'.repeat(5000)], 'r'); log.push(box.send());", maxUrl=1000)
        self.assertEqual((out['log'][0]['count'], out['log'][0]['left']), (1, 0))

    def test_the_issue_body_is_the_one_issue_form_reads_and_writes(self):
        rows = [['award', 'Asha Rao', 'helped', '1'], ['rename', 'Zoë "Z" Ng', 'Zoë, Ng']]
        out = run(f"log.push(issueBody('b7', {json.dumps(rows)}));")
        self.assertEqual(out['log'][0], issue_form.batch_body('b7', rows))
        self.assertEqual(issue_form.command('Facilitator: Changes', out['log'][0]), ['batch', 'b7', json.dumps(rows)])


@unittest.skipUnless(shutil.which('node'), 'needs Node.js to run changes.js')
class SettleTests(unittest.TestCase):
    SENT = f"box.add({AWARD}, 'a'); box.add({MARK}, 'm'); box.send();"

    def states(self, out):
        return [(r['state'], r.get('reason', ''), r.get('change')) for r in out['rows']]

    def test_each_row_takes_its_own_outcome(self):
        out = run(self.SENT + "log.push(box.settle({ b1: { rows: [{ ok: true, change: 'c9' }, { ok: false, message: 'No lesson fizzbuzz' }] } }));")
        self.assertEqual(out['log'], [{'landed': True, 'waiting': False}])
        self.assertEqual(self.states(out), [('done', '', 'c9'), ('failed', 'No lesson fizzbuzz', None)])

    def test_a_refused_batch_fails_every_row_with_its_reason(self):
        out = run(self.SENT + "log.push(box.settle({ b1: { error: 'Batch b1 was applied already.', rows: [] } }));")
        self.assertEqual(out['log'], [{'landed': False, 'waiting': False}])
        self.assertEqual(self.states(out), [('failed', 'Batch b1 was applied already.', None)] * 2)

    def test_a_row_missing_from_the_batch_fails(self):
        out = run(self.SENT + "box.settle({ b1: { rows: [{ ok: true }] } });")
        self.assertEqual(self.states(out)[1], ('failed', 'Not in the batch GitHub received.', None))

    def test_not_made_yet_keeps_waiting_until_it_gives_up(self):
        out = run(self.SENT + "log.push(box.settle({})); clock.t += 600001; log.push(box.settle({}));")
        self.assertEqual(out['log'], [{'landed': False, 'waiting': True}, {'landed': False, 'waiting': False}])
        self.assertEqual(out['rows'][0]['state'], 'failed')
        self.assertIn('If you did not press Submit new issue, try again', out['rows'][0]['reason'])

    def test_unreadable_says_why_and_gives_up_pointing_at_the_issue(self):
        out = run(self.SENT + "box.settle(null, { message: 'GitHub could not be reached' });"
                  "log.push(box.rows()[0].reason); clock.t += 600001; box.settle(null, { message: 'GitHub could not be reached' });")
        self.assertEqual(out['log'], ['GitHub could not be reached'])
        self.assertEqual(out['rows'][0]['reason'], 'GitHub could not be reached. The issue on GitHub says whether it was made.')

    def test_limited_reads_never_give_up(self):
        out = run(self.SENT + "clock.t += 3600000; log.push(box.settle(null, { message: 'GitHub asks the page to wait until 14:05', limited: true }));")
        self.assertEqual(out['log'], [{'landed': False, 'waiting': True}])
        self.assertEqual(self.states(out)[0], ('waiting', 'GitHub asks the page to wait until 14:05', None))


if __name__ == '__main__':
    unittest.main()
