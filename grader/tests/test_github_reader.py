"""github-reader.js: the facilitator page's one way of reading from GitHub without a token, and of polling it.

Run in Node.js with a stand-in fetch and a stand-in clock, so a test says what GitHub answers and when, and sees
what the reader asked for, what it made of each answer, and how its polls were paced.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

READER_JS = Path(__file__).resolve().parents[2] / 'github-reader.js'

# The harness: a clock and timers that only move when the scenario says, a fetch that answers from `answers` in
# turn ({status, body, headers}, or {throws} for a network failure, or {badBody} for a body that fails to arrive),
# and the scenario itself, a JS async function body given (reader, wait, log).
_RUN = r'''
const fs = require('fs'), vm = require('vm');
const { answers, scenario, options } = JSON.parse(fs.readFileSync(0, 'utf8'));
let clock = 1_000_000;
const timers = [];
const sleep = (ms) => new Promise((resolve) => timers.push({ at: clock + ms, resolve }));
async function wait(ms) {  // let time pass, running every timer due on the way
  const end = clock + ms;
  for (;;) {
    for (let i = 0; i < 20; i++) await Promise.resolve();
    timers.sort((a, b) => a.at - b.at);
    if (!timers.length || timers[0].at > end) break;
    const t = timers.shift();
    clock = t.at;
    t.resolve();
  }
  clock = end;
  for (let i = 0; i < 20; i++) await Promise.resolve();
}
const requests = [];
const fetch = async (url, init) => {
  const a = answers.length ? answers.shift() : { status: 304 };
  if (a.throws) throw new TypeError(a.throws);
  requests.push({ url, ifNoneMatch: (init.headers || {})['If-None-Match'] || null, at: clock });
  const headers = a.headers || {};
  return { status: a.status, ok: a.status >= 200 && a.status < 300, headers: { get: (k) => headers[k.toLowerCase()] ?? null },
           text: async () => { if (a.badBody) throw new TypeError('connection reset'); return typeof a.body === 'string' ? a.body : JSON.stringify(a.body); } };
};
const ctx = {}; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const reader = vm.runInContext('githubReader', ctx)({ fetch, now: () => clock, sleep, ...options });
const log = [];
(async () => {
  await new Function('reader', 'wait', 'log', 'return (async () => {' + scenario + '})()')(reader, wait, log);
  process.stdout.write(JSON.stringify({ log, requests, clock }));
})().catch((e) => { process.stderr.write(String(e.stack || e)); process.exit(1); });
'''


def run(scenario, answers=(), **options):
    r = subprocess.run(['node', '-e', _RUN, str(READER_JS)], capture_output=True, text=True, timeout=60,
                       input=json.dumps({'scenario': scenario, 'answers': list(answers), 'options': options}))
    if r.returncode:
        raise AssertionError('github-reader.js failed in Node:\n' + r.stderr)
    return json.loads(r.stdout)


URL = 'https://api.github.com/repos/o/board/contents/grader/batches.json?ref=main'
MINUTE, HOUR = 60 * 1000, 3600 * 1000
READ = f"log.push(await reader.read('{URL}', {{ json: true }}));"


def reads(n):
    return READ * n


@unittest.skipUnless(shutil.which('node'), 'needs Node.js to run github-reader.js')
class ReadTests(unittest.TestCase):
    def test_an_unchanged_answer_comes_from_the_cache_and_asks_with_its_etag(self):
        got = run(reads(2), [{'status': 200, 'body': {'b1': {}}, 'headers': {'etag': '"v1"'}}, {'status': 304}])
        self.assertEqual([(v['status'], v.get('value')) for v in got['log']], [('ok', {'b1': {}}), ('unchanged', {'b1': {}})])
        self.assertEqual([r['ifNoneMatch'] for r in got['requests']], [None, '"v1"'])

    def test_a_file_not_there_yet_is_missing_not_an_error(self):
        self.assertEqual(run(READ, [{'status': 404, 'body': {'message': 'Not Found'}}])['log'][0]['status'], 'missing')

    def test_a_body_that_never_arrives_is_an_error_and_leaves_no_etag_behind(self):
        got = run(reads(2), [{'status': 200, 'badBody': True, 'headers': {'etag': '"v1"'}}, {'status': 200, 'body': {'x': 1}}])
        self.assertEqual([v['status'] for v in got['log']], ['error', 'ok'])
        self.assertIsNone(got['requests'][1]['ifNoneMatch'], 'an ETag without its answer would turn the next 304 into nothing')

    def test_json_that_is_not_json_is_an_error_not_text(self):
        self.assertEqual(run(READ, [{'status': 200, 'body': 'not { json'}])['log'][0]['status'], 'error')

    def test_a_server_error_or_a_plain_403_is_an_error_not_a_limit(self):
        got = run(reads(2), [{'status': 502, 'body': 'Bad gateway'}, {'status': 403, 'body': {'message': 'Resource not accessible'}}])
        self.assertEqual([v['status'] for v in got['log']], ['error', 'error'])


@unittest.skipUnless(shutil.which('node'), 'needs Node.js to run github-reader.js')
class LimitTests(unittest.TestCase):
    def test_when_github_says_the_limit_is_reached_it_waits_until_githubs_reset(self):
        reset = (1_000_000 + 20 * MINUTE) // 1000  # in 20 minutes, as GitHub gives it: seconds since 1970
        got = run(READ + 'await wait(10 * 60000);' + READ + 'await wait(11 * 60000);' + READ,
                  [{'status': 403, 'body': {'message': 'API rate limit exceeded'}, 'headers': {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': str(reset)}},
                   {'status': 200, 'body': {}}])
        self.assertEqual([(v['status'], v.get('by')) for v in got['log']], [('limited', 'github'), ('limited', 'github'), ('ok', None)])
        self.assertEqual(got['log'][0]['until'], reset * 1000)
        self.assertEqual(len(got['requests']), 2, 'nothing is asked while GitHub is limiting reads')

    def test_retry_after_comes_before_the_reset_time(self):
        reset = (1_000_000 + 20 * MINUTE) // 1000
        got = run(READ, [{'status': 403, 'body': {}, 'headers': {'retry-after': '120', 'x-ratelimit-reset': str(reset)}}])
        self.assertEqual(got['log'][0]['until'], 1_000_000 + 2 * MINUTE)

    def test_a_secondary_limit_without_headers_waits_a_minute(self):
        got = run(READ + 'await wait(30000);' + READ + 'await wait(31000);' + READ,
                  [{'status': 403, 'body': {'message': 'You have exceeded a secondary rate limit.'}}, {'status': 200, 'body': {}}])
        self.assertEqual([v['status'] for v in got['log']], ['limited', 'limited', 'ok'])

    def test_its_own_budget_pauses_reads_and_says_it_is_the_page_not_github(self):
        # Unchanged answers count too: without a token GitHub counts 304s against its 60 an hour.
        got = run(reads(4) + f'await wait({HOUR});' + READ, budget=3)
        self.assertEqual([(v['status'], v.get('by')) for v in got['log']],
                         [('unchanged', None)] * 3 + [('limited', 'page'), ('unchanged', None)])
        self.assertEqual(len(got['requests']), 4)

    def test_a_read_that_never_reached_github_costs_nothing(self):
        got = run(reads(3), [{'throws': 'offline'}, {'status': 304}, {'status': 304}], budget=2)
        self.assertEqual([v['status'] for v in got['log']], ['error', 'unchanged', 'unchanged'])


POLL = '''
const steps = [];
const result = await Promise.race([
  reader.poll({ first: %(first)d, every: %(every)d, giveUpAfter: %(give_up)s,
                step: async () => { const v = await reader.read('%(url)s', { json: true }); steps.push(v.status);
                                    return v.status === 'ok' && v.value.done ? 'done' : v.status === 'error' ? 'error' : 'again'; } }),
  wait(%(run_for)d).then(() => 'still polling')]);
log.push({ result, steps });
'''


def poll(answers, first=MINUTE, every=MINUTE, give_up='Infinity', run_for=HOUR, budget=600, **options):
    # A budget of 600 an hour lets one poller keep its own pace; the budget's effect on pace is tested on its own.
    got = run(POLL % {'first': first, 'every': every, 'give_up': give_up, 'url': URL, 'run_for': run_for}, answers, budget=budget, **options)
    return got['log'][0], got['requests']


@unittest.skipUnless(shutil.which('node'), 'needs Node.js to run github-reader.js')
class PollTests(unittest.TestCase):
    def test_polls_at_its_pace_until_done(self):
        result, requests = poll([{'status': 200, 'body': {}}, {'status': 304}, {'status': 200, 'body': {'done': True}}])
        self.assertEqual(result['result'], 'done')
        self.assertEqual([r['at'] - 1_000_000 for r in requests], [MINUTE, 2 * MINUTE, 3 * MINUTE])

    def test_gives_up_after_its_time_limit(self):
        result, requests = poll([], give_up=5 * MINUTE)
        self.assertEqual(result['result'], 'gave up')
        self.assertEqual(len(requests), 5)

    def test_does_not_give_up_while_github_is_limiting_reads(self):
        reset = (1_000_000 + 30 * MINUTE) // 1000
        result, requests = poll([{'status': 403, 'body': {}, 'headers': {'x-ratelimit-remaining': '0', 'x-ratelimit-reset': str(reset)}},
                                 {'status': 200, 'body': {'done': True}}], give_up=5 * MINUTE)
        self.assertEqual(result['result'], 'done')
        self.assertEqual(requests[1]['at'], reset * 1000, 'it waits out the limit, then reads')

    def test_slows_down_after_errors(self):
        result, requests = poll([{'status': 502, 'body': ''}] * 3 + [{'status': 200, 'body': {'done': True}}])
        gaps = [b['at'] - a['at'] for a, b in zip(requests, requests[1:])]
        self.assertEqual(gaps, [2 * MINUTE, 4 * MINUTE, 8 * MINUTE])

    def test_two_pollers_together_stay_within_the_budget_for_an_hour(self):
        # Waiting changes and Grade now, each wanting a read a minute, for an hour: never more than the budget,
        # and never paused by the page's own limit (the pace slows instead).
        both = '''
        const statuses = [];
        const step = async () => { statuses.push((await reader.read('%s', { json: true })).status); return 'again'; };
        reader.poll({ first: 30000, every: 60000, step });
        reader.poll({ first: 60000, every: 60000, step });
        await wait(%d);
        log.push(statuses);
        ''' % (URL, HOUR)
        got = run(both, budget=50)
        self.assertLessEqual(len(got['requests']), 50)
        self.assertGreaterEqual(len(got['requests']), 40, 'still reading at a useful pace')
        self.assertNotIn('limited', got['log'][0])


if __name__ == '__main__':
    unittest.main()
