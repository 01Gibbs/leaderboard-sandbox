// The facilitator page's Changes box, without the page: what waits, what is sent, and what became of each row.
//  - add: a change waits (state queued) unless the same one already waits or is sent, or 40 already wait;
//  - send: every waiting row goes in one issue ("Facilitator: Changes", read by grader/issue_form.py), numbered
//    1, 2, ... in the batch; what does not fit in GitHub's address waits for the next send;
//  - settle: once grader/batches.json has the batch, each row is done (with its change id, for undo) or failed
//    (with why). Until then it waits, and after `giveUp` it fails, saying where to look; never while GitHub limits
//    reads (`unreadable.limited`), which only says why.
// The page draws `rows()` and decides nothing about them.
const changeLines = (argsList) => argsList.map((a) => JSON.stringify(a)).join('\n');  // one change a line
function issueBody(batch, argsList) {  // as grader/issue_form.py batch_body: a test holds the two to the same text
  return `### Batch\n\n${batch}\n\n### Changes\n\n` + changeLines(argsList);
}

function changesBox({ repo, giveUp, newBatchId, now = () => Date.now(), maxRows = 40, maxUrl = 7000 }) {
  // maxUrl: GitHub refuses (414) a filled-in address that is too long.
  let rows = [], nextKey = 1;
  const isOpen = (r) => r.state === 'queued' || r.state === 'waiting';
  const drop = (key) => { rows = rows.filter((r) => r.key !== key); };
  const issueUrl = (batch, sent) => `https://github.com/${repo}/issues/new?` + new URLSearchParams({
    template: 'facilitator-changes.yml', title: 'Facilitator: Changes', batch, changes: changeLines(sent.map((r) => r.args)) });

  function add(args, text) {  // null when added; otherwise {say} (nothing wrong) or {error}
    if (rows.some((r) => isOpen(r) && JSON.stringify(r.args) === JSON.stringify(args))) return { say: 'Already in Changes.' };
    if (rows.filter((r) => r.state === 'queued').length >= maxRows) return { error: `Send these ${maxRows} first.` };
    rows.push({ key: nextKey++, args, text, state: 'queued' });
    return null;
  }

  function send() {  // null when nothing waits; otherwise the issue to open and how many are left for next time
    let sent = rows.filter((r) => r.state === 'queued');
    if (!sent.length) return null;
    const batch = newBatchId();
    while (sent.length > 1 && issueUrl(batch, sent).length > maxUrl) sent = sent.slice(0, -1);
    const url = issueUrl(batch, sent), at = now();
    sent.forEach((r, i) => Object.assign(r, { state: 'waiting', batch, row: i + 1, sentAt: at, url, reason: '' }));
    return { batch, url, title: 'Facilitator: Changes', body: issueBody(batch, sent.map((r) => r.args)), count: sent.length,
             left: rows.filter((r) => r.state === 'queued').length };
  }

  function settle(batches, unreadable = null) {  // batches.json (or null when it could not be read)
    let landed = false;
    rows.filter((r) => r.state === 'waiting').forEach((r) => {
      const b = batches && batches[r.batch];
      if (b) {
        const o = b.error ? { ok: false, message: b.error } : b.rows[r.row - 1] || { ok: false, message: 'Not in the batch GitHub received.' };
        landed = landed || o.ok;
        Object.assign(r, o.ok ? { state: 'done', change: o.change, reason: '' } : { state: 'failed', reason: o.message });
      } else if (unreadable && unreadable.limited) {
        r.reason = unreadable.message;
      } else if (now() - r.sentAt > giveUp) {
        Object.assign(r, { state: 'failed', reason: unreadable
          ? `${unreadable.message}. The issue on GitHub says whether it was made.`
          : 'GitHub has not made it yet. If you did not press Submit new issue, try again; otherwise the issue on GitHub says why.' });
      } else {
        r.reason = unreadable ? unreadable.message : '';
      }
    });
    return { landed, waiting: rows.some((r) => r.state === 'waiting') };
  }

  return {
    rows: () => rows,
    add,
    send,
    settle,
    remove: drop,  // a waiting row taken out, or a failed one dismissed
    retry(key) { const r = rows.find((x) => x.key === key); drop(key); return r ? add(r.args, r.text) : null; },
    clearDone() { rows = rows.filter((r) => r.state !== 'done'); },
    pending: (test) => rows.some((r) => isOpen(r) && test(r.args)),  // a change of this kind waits or is sent
  };
}
