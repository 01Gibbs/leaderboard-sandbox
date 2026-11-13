"""The leaderboard's rules, read from the page's own scoring.js so the grader and the page always agree.

The RULES block in scoring.js (points, status words, columns, delimiters) is the single copy.
parse_csv, norm_header, norm_status and to_int are ports of scoring.js's functions of the same names, so the grader
reads participants.csv exactly as the page does. Points and ranking exist only in scoring.js.
grader/tests/test_rules.py runs both on the same files to prove they agree.
"""
import json
import re
from pathlib import Path

SCORING_JS = Path(__file__).resolve().parents[1] / 'scoring.js'


def _load(path=SCORING_JS):
    text = Path(path).read_text(encoding='utf-8')
    m = re.search(r'/\* rules:start \*/(.*?)/\* rules:end \*/', text, re.S)
    if not m:
        raise RuntimeError(f'{path} has no /* rules:start */ ... /* rules:end */ block')
    return json.loads(m.group(1))


RULES = _load()
STATUSES = ['none', 'submitted', 'correct']  # lowest to highest
RANK = {s: i for i, s in enumerate(STATUSES)}
BASE_COLUMNS = list(RULES['baseColumns'])
COUNTS = list(RULES['counts'])
EARLY_BONUS = RULES['earlyBonus']  # the grader works out this column; facilitators do not edit it
GENERATED = [EARLY_BONUS['column']]


def parse_csv(text):
    """Rows of cells, as scoring.js's parseCSV reads them. Returns (rows, delimiter, had_bom)."""
    bom = text.startswith('﻿')
    text = text[1:] if bom else text
    first = re.split(r'\r?\n', text, maxsplit=1)[0]
    delim = sorted(RULES['delimiters'], key=lambda ch: -first.count(ch))[0]  # stable, like JS sort
    out, row, cur, q, i = [], [], '', False, 0
    while i < len(text):
        c = text[i]
        if q:
            if c == '"':
                if text[i + 1:i + 2] == '"':
                    cur += '"'
                    i += 1
                else:
                    q = False
            else:
                cur += c
        elif c == '"':
            q = True
        elif c == delim:
            row.append(cur)
            cur = ''
        elif c in '\r\n':
            if c == '\r' and text[i + 1:i + 2] == '\n':
                i += 1
            row.append(cur)
            cur = ''
            out.append(row)
            row = []
        else:
            cur += c
        i += 1
    if cur != '' or row:
        row.append(cur)
        out.append(row)
    return [r for r in out if any(v.strip() for v in r)], delim, bom


def norm_header(h):
    key = re.sub(r'[\s-]+', '_', h.strip().lower())
    return RULES['headerAliases'].get(key, key)


def norm_status(v):
    s = str(v or '').strip().lower()
    for status in ('correct', 'submitted'):
        if s in RULES['statuses'][status]:
            return status
    return 'none'


def to_int(v):
    """Like JavaScript's parseInt: leading whole number, else 0 ("7.5" -> 7, "abc" -> 0)."""
    m = re.match(r'([+-]?[0-9]+)', str(v or '').strip())
    return int(m.group(1)) if m else 0
