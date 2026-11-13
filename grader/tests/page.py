"""The page's own scoring.js, run in Node.js, for tests that need to know what the leaderboard shows.

Scoring lives only in scoring.js; the grader never computes points. Tests using this skip without Node:
decorate them with @needs_node.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

SCORING_JS = Path(__file__).resolve().parents[2] / 'scoring.js'
needs_node = unittest.skipUnless(shutil.which('node'), "needs Node.js to run the page's scoring.js")

_SCORE = r'''
const fs = require('fs'), vm = require('vm');
const ctx = {}; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const { text, keys } = JSON.parse(fs.readFileSync(0, 'utf8'));
const tracks = keys.map((k) => ({ k }));
const read = vm.runInContext('readParticipants', ctx)(text, tracks);
const pointsOf = vm.runInContext('pointsOf', ctx);
process.stdout.write(JSON.stringify({ skipped: read.skipped, rows: read.rows.map((p) => ({ ...p, points: pointsOf(p, tracks) })) }));
'''


def read(text, keys):
    """participants.csv text as the page reads it: {'rows': [{name, tracks, stretch, prStretch, helped, bonus, points}],
    'skipped': n}."""
    r = subprocess.run(['node', '-e', _SCORE, str(SCORING_JS)], input=json.dumps({'text': text, 'keys': keys}),
                       capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise AssertionError('scoring.js failed in Node:\n' + r.stderr)
    return json.loads(r.stdout)


def points(text, keys):
    """{name: points} for every row the page shows."""
    return {p['name']: p['points'] for p in read(text, keys)['rows']}
