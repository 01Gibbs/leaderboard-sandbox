// The facilitator page's one way of reading from GitHub without a token, and of polling it. So that:
//  - each read asks only for what changed (an ETag), and an unchanged answer comes from the cache;
//  - every read on the page shares one budget. GitHub allows 60 reads an hour without a token, per network (so
//    shared with everyone at the venue), and counts unchanged answers too. The page keeps to `budget` an hour,
//    and its polls space themselves out so that together they stay within it;
//  - when GitHub says the limit is reached (403 or 429), nothing more is asked until the time GitHub gives;
//  - a poll slows down after errors, waits out a limit, and gives up after its time limit (but not while limited).
// Each read gets a verdict: ok, unchanged (both readable: see `readable`), missing (404: not there yet), limited
// (`by` 'github' or 'page', and `until`, when reading can start again) or error (`reason`).
function githubReader({ fetch, now = () => Date.now(), sleep = (ms) => new Promise((r) => setTimeout(r, ms)), budget = 50, perMs = 3600 * 1000 }) {
  const etags = {}, cache = {};
  let asked = [];  // when each read that reached GitHub was made, within the last `perMs`
  let githubUntil = 0;  // GitHub's own limit: no reads before this
  let polling = 0;  // how many polls are running, sharing the budget

  function limit() {
    const t = now();
    asked = asked.filter((at) => t - at < perMs);
    if (githubUntil > t) return { by: 'github', until: githubUntil };
    if (asked.length >= budget) return { by: 'page', until: asked[0] + perMs };
    return null;
  }

  function rateLimited(res, body) {
    if (res.status === 429) return true;
    if (res.status !== 403) return false;
    return res.headers.get('x-ratelimit-remaining') === '0' || res.headers.get('retry-after') !== null || /rate limit/i.test(body);
  }

  async function read(url, { accept = 'application/vnd.github+json', json = false } = {}) {
    const limited = limit();
    if (limited) return { status: 'limited', ...limited };
    const headers = { Accept: accept, 'X-GitHub-Api-Version': '2022-11-28' };
    if (etags[url]) headers['If-None-Match'] = etags[url];
    let res, text;
    try {
      res = await fetch(url, { headers, cache: 'no-store' });
      asked.push(now());
      text = res.status === 304 ? '' : await res.text();
    } catch (e) {
      return { status: 'error', reason: `could not reach GitHub (${e.message || e})` };
    }
    if (res.status === 304) return { status: 'unchanged', value: cache[url] };
    if (res.status === 404) return { status: 'missing' };
    if (rateLimited(res, text)) {  // GitHub: retry-after first, then the reset time, else at least a minute
      const retry = Number(res.headers.get('retry-after')) * 1000, reset = Number(res.headers.get('x-ratelimit-reset')) * 1000;
      githubUntil = retry ? now() + retry : reset > now() ? reset : now() + 60 * 1000;
      return { status: 'limited', by: 'github', until: githubUntil };
    }
    if (!res.ok) return { status: 'error', reason: `GitHub said ${res.status}` };
    let value = text;
    if (json) {
      try { value = JSON.parse(text); } catch (e) { return { status: 'error', reason: 'GitHub sent something that is not JSON' }; }
    }
    etags[url] = res.headers.get('ETag');  // only now: an ETag is worth keeping only with the answer it stands for
    cache[url] = value;
    return { status: 'ok', value };
  }

  const readable = (verdict) => verdict.status === 'ok' || verdict.status === 'unchanged';

  // Calls `step` after `first`, then every `every` (more apart when other polls share the budget, twice as long after
  // each error, up to 10 minutes), until it returns 'done' or `giveUpAfter` has passed. `step` returns 'done',
  // 'again' or 'error'. Resolves 'done' or 'gave up'.
  async function poll({ first, every, giveUpAfter = Infinity, step }) {
    const started = now();
    let wait = first, errors = 0;
    polling += 1;
    try {
      for (;;) {
        const limited = limit();
        await sleep(Math.max(wait, limited ? limited.until - now() : 0));
        const said = await step();
        if (said === 'done') return 'done';
        errors = said === 'error' ? errors + 1 : 0;
        if (now() - started >= giveUpAfter && !limit()) return 'gave up';
        wait = Math.min(Math.max(every, perMs * polling / budget) * 2 ** errors, Math.max(every, 10 * 60 * 1000));
      }
    } finally {
      polling -= 1;
    }
  }

  return { read, readable, poll, limit };
}
