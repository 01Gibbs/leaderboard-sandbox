// The facilitator forms: one per facilitator-*.yml workflow (docs/adr/0002), with the same inputs. The facilitator
// page (facilitator.html) shows these and starts the workflow; grader/tests/test_facilitator_page.py fails if a
// form and its workflow disagree. Labels and hints are what a facilitator reads, so keep them plain.
//
// A field's `kind` says how the page asks for it: "person" (anyone on the board), "lesson" (from lessons.json),
// "choice" (one of `options`), or "text".

const FORMS = [
  {
    id: 'award', workflow: 'facilitator-award.yml', title: 'Award points',
    help: 'Stretch tasks, helping someone, or bonus points. A minus sign takes them away.',
    fields: [
      { input: 'person', label: 'Person', kind: 'person', required: true },
      { input: 'kind', label: 'What for', kind: 'choice', options: ['helped', 'stretch', 'bonus'], required: true },
      { input: 'amount', label: 'How many', kind: 'text', value: '1', required: false,
        hint: 'Helps or stretch tasks, or bonus points. Use -1 to take one away.' },
    ],
  },
  {
    id: 'mark', workflow: 'facilitator-mark.yml', title: 'Mark an exercise',
    help: 'Set a result by hand, for an exercise you checked yourself. It cannot go below what a pull request earned.',
    fields: [
      { input: 'person', label: 'Person', kind: 'person', required: true },
      { input: 'lesson', label: 'Exercise', kind: 'lesson', required: true },
      { input: 'status', label: 'Result', kind: 'choice', options: ['correct', 'submitted', 'none'], required: true },
    ],
  },
  {
    id: 'add', workflow: 'facilitator-add.yml', title: 'Add a person',
    help: 'Someone who has not opened a pull request yet. Once they do, it counts for this row.',
    fields: [
      { input: 'name', label: 'Full name', kind: 'text', required: true },
      { input: 'github', label: 'GitHub username', kind: 'text', required: false, hint: 'If you know it.' },
    ],
  },
  {
    id: 'rename', workflow: 'facilitator-rename.yml', title: 'Rename a person',
    help: 'Show a real name instead of a GitHub username. Their pull requests still count.',
    fields: [
      { input: 'person', label: 'Person', kind: 'person', required: true },
      { input: 'new_name', label: 'Name to show', kind: 'text', required: true },
    ],
  },
  {
    id: 'merge', workflow: 'facilitator-merge.yml', title: 'Merge duplicate people',
    help: 'One person on two rows. The row to keep gets the higher value of every column.',
    fields: [
      { input: 'keep', label: 'Row to keep', kind: 'person', required: true, hint: 'Its name stays.' },
      { input: 'duplicate', label: 'Duplicate row', kind: 'person', required: true },
    ],
  },
  {
    id: 'undo', workflow: 'facilitator-undo.yml', title: 'Undo the last change',
    help: 'Reverses the most recent facilitator change, whoever made it. Graded results are kept.',
    fields: [],
  },
];
