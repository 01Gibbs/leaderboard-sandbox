#!/usr/bin/env bash
# Usage: grader/run_and_push.sh "<commit title, or empty to use the command's first line of output>" "<command>"
#
# Used by the workflows that change participants.csv. Runs the command on the latest main, commits what it
# changed and pushes. If someone else pushed first, it starts again from their version, so two changes made
# at the same time both land and neither works from an out-of-date file.
set -euo pipefail
title=$1
command=$2
summary=${GITHUB_STEP_SUMMARY:-/dev/null}
attempt_summary=$(mktemp)

git config user.name "leaderboard-bot"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3 4 5; do
  git fetch -q origin main
  git reset -q --hard origin/main
  git clean -fdq -- grader/fixtures  # nothing left over (an earlier attempt's) can be staged with the lessons
  : > "$attempt_summary"
  # A failing command (for example a misspelled name) stops here: nothing is committed. Exit 3 says it was the
  # command that said no, so a caller can tell that from failing to save, which exits 1 (or git's own code).
  if ! output=$(GITHUB_STEP_SUMMARY=$attempt_summary bash -c "$command"); then
    cat "$attempt_summary" >> "$summary"
    exit 3
  fi
  echo "$output"
  # The state files, and the lessons and their pinned tests (added or removed from the facilitator page). -A so
  # a removed lesson's tests are removed too.
  for f in participants.csv grader/results.json grader/history.json grader/batches.json lessons.json grader/fixtures; do
    if [[ -e $f ]]; then git add -A -- "$f"; fi
  done
  if git diff --cached --quiet; then
    cat "$attempt_summary" >> "$summary"
    echo "Nothing changed."
    exit 0
  fi
  git commit -q -m "${title:-Leaderboard: $(head -1 <<< "$output")}" -m "By @${GITHUB_ACTOR:-unknown}."
  if git push -q origin HEAD:main; then
    cat "$attempt_summary" >> "$summary"
    exit 0
  fi
  echo "Someone else changed the leaderboard at the same time; redoing this on top of their change." >&2
  sleep $((attempt * 3))
done
echo "Could not save after 5 attempts. Run the action again." >&2
exit 1
