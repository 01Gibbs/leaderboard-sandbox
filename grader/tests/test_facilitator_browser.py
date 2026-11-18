"""End to end: the facilitator page in a real browser, on facilitator_walkthrough.py's practice copy.

Each test is a facilitator's journey (docs/research/facilitator-ui.md): pick a person, act, see the change wait in
the Changes box, send it, and see it done (or not, with the reason), undoable on its own. Slow tier. Needs Playwright
with Chromium:
    uv run --no-project --with playwright python -m playwright install chromium
    uv run --no-project --with playwright python -m unittest grader/tests/test_facilitator_browser.py
It skips when Playwright or its browser is missing.
"""
import csv
import io
import json
import re
import shutil
import sys
import threading
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / 'grader'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import facilitator_walkthrough  # noqa: E402
from tiers import slow  # noqa: E402

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # not installed: the class below is skipped
    sync_playwright = None


@slow
@unittest.skipUnless(sync_playwright, 'needs Playwright (see the module docstring)')
class FacilitatorJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:  # browser not installed
            cls.pw.stop()
            raise unittest.SkipTest(f'Playwright has no Chromium: {e}') from None

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.server, url, self.folder = facilitator_walkthrough.serve(0)
        self.base = url.split('/walkthrough/')[0]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.page = self.open('/facilitator.html?practice#people')
        expect(self.page.locator('#who')).to_have_text('Practising')
        expect(self.page.locator('#roster-list li').first).to_be_visible()

    def open(self, path, width=1280):
        page = self.browser.new_page(viewport={'width': width, 'height': 900})
        self.addCleanup(page.close)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        self.addCleanup(lambda: self.assertEqual(errors, [], 'JavaScript errors on the page'))
        page.goto(self.base + path)
        return page

    # ---------- helpers ----------

    def pick(self, name):
        self.page.get_by_role('tab', name='People').click()
        self.page.locator('#find').fill(name)
        self.page.locator('#find').press('Enter')
        expect(self.page.locator('#person h2')).to_have_text(name)

    def queued(self):
        return self.page.locator('#queue li')

    def send(self):
        """Send everything in the Changes box; wait until every row is done or not done."""
        self.page.locator('#send').click()
        expect(self.page.locator('#queue li.waiting').first).to_be_attached()  # sent
        expect(self.page.locator('#queue li.queued, #queue li.waiting')).to_have_count(0, timeout=15000)

    def sheet(self):
        with urllib.request.urlopen(self.base + '/participants.csv') as r:
            return {row['name']: row for row in csv.DictReader(io.StringIO(r.read().decode()))}

    def state(self, name):
        with urllib.request.urlopen(self.base + f'/practice-api/repos/practice/leaderboard/contents/grader/{name}.json') as r:
            return json.load(r)

    # ---------- journeys ----------

    def test_pick_a_person_and_see_where_they_stand(self):
        self.pick('Ben Okafor')
        pane = self.page.locator('#person')
        expect(pane).to_contain_text('@benok')
        expect(pane).to_contain_text(re.compile(r'\d+ points · rank \d+'))
        expect(pane.get_by_role('button', name=re.compile('Mark Ben Okafor.s .* correct'))).not_to_have_count(0)

    def test_give_a_help_send_it_and_see_it_done(self):
        helped = int(self.sheet()['Asha Rao']['helped'] or 0)
        self.pick('Asha Rao')
        self.page.get_by_role('button', name='Give Asha Rao a help').click()
        expect(self.queued()).to_have_count(1)
        expect(self.queued().first).to_contain_text('Give 1 help to Asha Rao.')
        expect(self.queued().first).to_contain_text('Not sent yet')
        self.send()
        self.assertEqual(int(self.sheet()['Asha Rao']['helped']), helped + 1)
        expect(self.queued()).to_have_count(0, timeout=5000)  # done rows fade out of the box
        expect(self.page.locator('#history li').first).to_contain_text('Gave 1 help to Asha Rao')
        expect(self.page.locator('#history li').first.get_by_role('button', name=re.compile('^Undo'))).to_be_visible()

    def test_several_changes_go_as_one_batch(self):
        self.pick('Asha Rao')
        self.page.get_by_role('button', name='Give Asha Rao a help').click()
        self.pick('Ben Okafor')
        self.page.get_by_role('button', name='Give Ben Okafor a stretch task').click()
        self.page.locator('#more').click()
        self.page.get_by_role('menuitem', name='Rename…').click()
        self.page.locator('#inline [name=new_name]').fill('Ben O')
        self.page.locator('#inline').get_by_role('button', name='Add to changes').click()
        expect(self.queued()).to_have_count(3)
        expect(self.page.locator('#send')).to_have_text('Send 3 changes')
        self.send()
        batches = self.state('batches')
        self.assertEqual(len(batches), 1, 'one issue for all three')
        self.assertEqual([r['ok'] for r in next(iter(batches.values()))['rows']], [True, True, True])
        self.assertIn('Ben O', self.sheet())

    def test_a_refused_change_stays_with_the_reason(self):
        lesson = json.loads((REPO / 'lessons.json').read_text())[0]
        self.pick('Asha Rao')  # her pull request on the first lesson passed (the practice copy's results)
        self.page.locator('#more').click()
        self.page.get_by_role('menuitem', name='Set a result…').click()
        self.page.locator('#inline [name=lesson]').select_option(lesson['key'])
        self.page.locator('#inline [name=status]').select_option('none')
        self.page.locator('#inline').get_by_role('button', name='Add to changes').click()
        self.page.get_by_role('button', name='Give Asha Rao a help').click()
        self.send()
        failed = self.page.locator('#queue li.failed')
        expect(failed).to_have_count(1)
        expect(failed).to_contain_text('graded correct')
        expect(self.page.locator('#history li').first).to_contain_text('Gave 1 help to Asha Rao')  # the other row went through
        failed.get_by_role('button', name='Dismiss').click()
        expect(self.queued()).to_have_count(0, timeout=5000)

    def test_undo_one_change_of_a_batch(self):
        self.pick('Asha Rao')
        self.page.get_by_role('button', name='Give Asha Rao a help').click()
        self.pick('Ben Okafor')
        self.page.get_by_role('button', name='Give Ben Okafor a help').click()
        before = self.sheet()
        self.send()
        asha = self.page.locator('#history li', has_text='Gave 1 help to Asha Rao')
        asha.get_by_role('button', name=re.compile('^Undo')).click()
        expect(self.queued().first).to_contain_text('Undo: Gave 1 help to Asha Rao')
        self.send()
        sheet = self.sheet()
        self.assertEqual(sheet['Asha Rao']['helped'], before['Asha Rao']['helped'])
        self.assertEqual(int(sheet['Ben Okafor']['helped'] or 0), int(before['Ben Okafor']['helped'] or 0) + 1)
        expect(self.page.locator('#history li', has_text='Gave 1 help to Asha Rao')).to_have_count(0)

    def test_award_several_people_at_once(self):
        self.page.locator('#multi').check()
        for name in ('Asha Rao', 'Ben Okafor', 'Chloe Martin'):
            self.page.get_by_role('checkbox', name='Select ' + name).check()
        expect(self.page.locator('#person h2')).to_have_text('3 selected')
        before = self.sheet()
        self.page.get_by_role('button', name='+1 help each').click()
        expect(self.queued()).to_have_count(3)
        self.send()
        after = self.sheet()
        for name in ('Asha Rao', 'Ben Okafor', 'Chloe Martin'):
            self.assertEqual(int(after[name]['helped'] or 0), int(before[name]['helped'] or 0) + 1, name)

    def test_add_someone_the_search_does_not_find(self):
        self.page.locator('#find').fill('Priya New')
        self.page.locator('#addRow').get_by_role('button', name='Add Priya New').click()
        self.page.locator('#inline [name=github]').fill('priya-n')
        self.page.locator('#inline').get_by_role('button', name='Add to changes').click()
        expect(self.queued().first).to_contain_text('Add Priya New (@priya-n).')
        self.send()
        self.assertIn('Priya New', self.sheet())
        self.page.locator('#find').fill('Priya')
        expect(self.page.locator('#roster-list li')).to_have_count(1)

    def test_merge_shows_what_the_row_will_be(self):
        self.page.locator('#find').fill('Dup Person')
        self.page.locator('#addRow').get_by_role('button', name='Add Dup Person').click()
        self.page.locator('#inline [name=github]').fill('dup-person')
        self.page.locator('#inline').get_by_role('button', name='Add to changes').click()
        self.send()
        self.pick('Asha Rao')
        self.page.locator('#more').click()
        self.page.get_by_role('menuitem', name='Same person as…').click()
        self.page.locator('#inline [name=other]').select_option('Dup Person')
        preview = self.page.locator('[data-tour="merge-preview"]')
        expect(preview).to_contain_text('asha-rao dup-person')
        self.page.locator('#inline').get_by_role('button', name='Add to changes').click()
        self.send()
        sheet = self.sheet()
        self.assertNotIn('Dup Person', sheet)
        self.assertEqual(sheet['Asha Rao']['github_username'], 'asha-rao dup-person')

    def test_checks_on_the_page_catch_mistakes_before_github(self):
        self.pick('Asha Rao')
        self.page.locator('#more').click()
        self.page.get_by_role('menuitem', name='Rename…').click()
        self.page.locator('#inline [name=new_name]').fill('Ben Okafor')
        self.page.locator('#inline').get_by_role('button', name='Add to changes').click()
        expect(self.page.locator('#error')).to_contain_text('Ben Okafor is already on the board')
        expect(self.queued()).to_have_count(0)

    def test_keyboard_shortcuts(self):
        self.page.locator('body').press('/')
        expect(self.page.locator('#find')).to_be_focused()
        self.page.keyboard.type('Chloe')
        self.page.keyboard.press('Enter')
        expect(self.page.locator('#person h2')).to_have_text('Chloe Martin')
        self.page.locator('#person h2').click()  # focus off the search box
        self.page.keyboard.press('h')
        self.page.keyboard.press('s')
        expect(self.queued()).to_have_count(2)
        self.page.keyboard.press('?')
        expect(self.page.locator('#keys')).to_be_visible()
        self.page.locator('#keysOn').uncheck()
        self.page.locator('#keysClose').click()
        self.page.keyboard.press('h')
        expect(self.queued()).to_have_count(2)  # turned off

    def test_works_on_a_phone_sized_screen(self):
        page = self.open('/facilitator.html?practice#people', width=375)
        expect(page.locator('#roster-list li').first).to_be_visible()
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 375, 'no sideways scrolling')
        boxes = [page.locator(s).bounding_box() for s in ('#roster', '#person', '#changes')]
        self.assertTrue(boxes[0]['y'] < boxes[1]['y'] < boxes[2]['y'], 'stacked: people, then the person, then changes')
        page.get_by_role('tab', name='Workshop').click()
        expect(page.locator('#lessonList li').first).to_be_visible()
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 375, 'no sideways scrolling')
        boxes = [page.locator(s).bounding_box() for s in ('#grading', '#lessonsPanel', '#changes')]
        self.assertTrue(boxes[0]['y'] < boxes[1]['y'] < boxes[2]['y'], 'stacked: grading, then lessons, then changes')

    def test_a_change_cannot_be_undone_twice_from_the_page(self):
        self.pick('Asha Rao')
        self.page.get_by_role('button', name='Give Asha Rao a help').click()
        self.send()
        undo = self.page.locator('#history li').first.get_by_role('button', name=re.compile('^Undo'))
        undo.click()
        expect(undo).to_be_disabled()
        expect(undo).to_have_text('Undo waiting')
        expect(self.queued()).to_have_count(1)

    def test_arrow_keys_move_through_the_people(self):
        find = self.page.locator('#find')
        find.focus()
        find.press('ArrowDown')
        find.press('ArrowDown')
        second = self.page.locator('#roster-list li').nth(1).get_attribute('data-name')
        expect(find).to_have_attribute('aria-activedescendant', 'person-1')
        find.press('Enter')
        expect(self.page.locator('#person h2')).to_have_text(second)

    def test_a_batch_refused_as_a_whole_shows_why_on_every_row(self):
        self.page.evaluate("queueRow(['grade'], 'Grade everything'); queueRow(['award', 'Asha Rao', 'helped', '1'], 'A help')")
        self.send()
        failed = self.page.locator('#queue li.failed')
        expect(failed).to_have_count(2)
        expect(failed.first).to_contain_text('cannot go in a batch')

    def test_a_change_github_never_makes_is_not_left_waiting(self):
        page = self.open('/facilitator.html?practice&timeout=2#people')
        page.route('**/practice-api/**/issues', lambda route: route.fulfill(status=201, body='{}'))  # sent, never applied
        expect(page.locator('#roster-list li').first).to_be_visible()
        page.locator('#find').fill('Asha Rao')
        page.locator('#find').press('Enter')
        page.get_by_role('button', name='Give Asha Rao a help').click()
        page.locator('#send').click()
        failed = page.locator('#queue li.failed')
        expect(failed).to_have_count(1, timeout=10000)
        expect(failed).to_contain_text('GitHub has not made it yet')
        failed.get_by_role('button', name='Try again').click()
        expect(page.locator('#queue li.queued')).to_have_count(1)

    def test_a_change_waiting_while_github_limits_reads_says_so_and_is_not_given_up(self):
        page = self.open('/facilitator.html?practice&timeout=2#people')
        refused = []

        def first_read_limited(route):  # GitHub refuses the first read, until 4 s from now; then answers as usual
            if refused:
                return route.continue_()
            refused.append(1)
            route.fulfill(status=403, content_type='application/json', body='{"message": "API rate limit exceeded"}',
                          headers={'x-ratelimit-remaining': '0', 'x-ratelimit-reset': str(int(time.time()) + 4)})
        page.route('**/practice-api/**/contents/grader/batches.json*', first_read_limited)
        expect(page.locator('#roster-list li').first).to_be_visible()
        page.locator('#find').fill('Asha Rao')
        page.locator('#find').press('Enter')
        page.get_by_role('button', name='Give Asha Rao a help').click()
        page.locator('#send').click()
        expect(page.locator('#queue li.waiting')).to_contain_text('GitHub is limiting how often this network can read it')
        # The limit outlasts the 2-second give-up: the change is still read, and done, not given up.
        expect(page.locator('#queue li.done')).to_have_count(1, timeout=15000)
        expect(page.locator('#queue li.failed')).to_have_count(0)

    # ---------- points: help and stretch count one at a time; only bonus has an amount ----------

    def more(self, item):
        self.page.locator('#more').click()
        self.page.get_by_role('menuitem', name=item).click()

    def test_bonus_points_ask_only_for_the_points(self):
        self.pick('Asha Rao')
        self.more('Bonus points…')
        expect(self.page.locator('#inline').get_by_label('Points', exact=True)).to_have_value('1')
        self.page.locator('#inline').get_by_label('Points', exact=True).fill('3')
        self.page.locator('#inline').get_by_role('button', name='Add to changes').click()
        expect(self.queued()).to_contain_text('Give 3 bonus points to Asha Rao.')

    def test_taking_away_a_help_or_a_stretch_takes_one_without_asking_how_many(self):
        self.pick('Asha Rao')
        self.page.get_by_role('button', name='Give Asha Rao a help').click()
        self.send()
        self.more('Take some away…')
        box = self.page.locator('#inline')
        box.get_by_label('What').select_option('helped')
        expect(box.get_by_label('Points', exact=True)).to_be_hidden()
        box.get_by_role('button', name='Add to changes').click()
        expect(self.page.locator('#queue li.queued')).to_contain_text('Take 1 help from Asha Rao.')

    def test_a_refused_take_away_keeps_its_box_open_and_says_why(self):
        self.pick('Chloe Martin')  # no stretch tasks to take
        self.more('Take some away…')
        box = self.page.locator('#inline')
        box.get_by_label('What').select_option('stretch')
        box.get_by_role('button', name='Add to changes').click()
        expect(box).to_be_visible()
        expect(self.page.locator('#error')).to_contain_text('Chloe Martin has 0 stretch tasks; cannot take away 1.')
        expect(self.queued()).to_have_count(0)

    def test_taking_away_bonus_points_asks_how_many_points(self):
        self.pick('Asha Rao')
        self.more('Take some away…')
        box = self.page.locator('#inline')
        box.get_by_label('What').select_option('bonus')
        box.get_by_label('Points', exact=True).fill('2')
        box.get_by_role('button', name='Add to changes').click()
        expect(self.queued()).to_contain_text('Take 2 bonus points from Asha Rao.')

    # ---------- the two tabs ----------

    def test_workshop_is_the_default_and_the_tabs_work_as_a_tab_list(self):
        page = self.open('/facilitator.html?practice')
        workshop, people = page.get_by_role('tab', name='Workshop'), page.get_by_role('tab', name='People')
        expect(workshop).to_have_attribute('aria-selected', 'true')
        expect(page.locator('#workshop-panel')).to_be_visible()
        expect(page.locator('#people-panel')).to_be_hidden()
        workshop.focus()
        page.keyboard.press('ArrowRight')
        expect(people).to_be_focused()
        expect(people).to_have_attribute('aria-selected', 'true')
        expect(page.locator('#people-panel')).to_be_visible()
        self.assertTrue(page.url.endswith('#people'), 'a tab can be linked')
        page.evaluate("location.hash = '#workshop'")  # a link back
        expect(workshop).to_have_attribute('aria-selected', 'true')
        expect(workshop).to_be_focused()
        page.evaluate("location.hash = '#people'")
        page.keyboard.press('ArrowRight')  # wraps round
        expect(workshop).to_be_focused()
        page.keyboard.press('End')
        expect(people).to_have_attribute('aria-selected', 'true')
        page.keyboard.press('Home')
        expect(workshop).to_have_attribute('aria-selected', 'true')
        expect(people).to_have_attribute('tabindex', '-1')

    def test_a_half_filled_form_survives_a_trip_to_the_other_tab_without_a_read(self):
        page = self.open('/facilitator.html?practice')
        expect(page.locator('#lessonList li').first).to_be_visible()
        reads = []
        page.on('request', lambda r: reads.append(r.url) if '/practice-api/' in r.url else None)
        page.locator('#addLesson summary').click()
        page.locator('#lessonRepo').fill('practice/half-done')
        page.get_by_role('tab', name='People').click()
        page.get_by_role('tab', name='Workshop').click()
        expect(page.locator('#lessonRepo')).to_have_value('practice/half-done')
        self.assertEqual(reads, [], 'switching tabs reads nothing')

    def test_slash_finds_a_person_from_either_tab_and_letters_act_only_on_people(self):
        page = self.open('/facilitator.html?practice')
        expect(page.locator('#lessonList li').first).to_be_visible()
        page.keyboard.press('/')
        expect(page.locator('#people-panel')).to_be_visible()
        expect(page.locator('#find')).to_be_focused()
        page.locator('#find').fill('Asha Rao')
        page.locator('#find').press('Enter')
        page.get_by_role('tab', name='Workshop').click()
        page.keyboard.press('h')
        expect(page.locator('#queue li')).to_have_count(0)

    def test_the_page_says_who_can_send_and_reads_little_on_load(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        reads = []
        page.context.route('https://github.com/**', lambda route: route.fulfill(body='GitHub', content_type='text/html'))
        page.context.route('https://api.github.com/**', lambda route: (reads.append(route.request.url), route.fulfill(status=404, body='{}')))
        page.goto(self.base + '/facilitator.html?repo=someone/board#people')
        page.locator('#find').fill('Asha Rao')
        page.locator('#find').press('Enter')
        page.get_by_role('button', name='Give Asha Rao a help').click()
        expect(page.locator('#sendHint')).to_contain_text("Only the leaderboard's collaborators can make changes.")
        self.assertLessEqual(len(reads), 4, f'reads on load: {reads}')  # GitHub allows 60 an hour without a token

    def test_the_changes_box_is_shared_by_both_tabs(self):
        self.pick('Asha Rao')
        self.page.get_by_role('button', name='Give Asha Rao a help').click()
        self.page.get_by_role('tab', name='Workshop').click()
        expect(self.queued()).to_have_count(1)
        self.page.locator('#lessonList li', has_text='Old exercise').get_by_role('button', name='Remove lesson Old exercise').click()
        expect(self.queued()).to_have_count(2)
        expect(self.page.locator('#send')).to_have_text('Send 2 changes')
        self.send()  # one Send for both tabs' changes
        expect(self.page.locator('#queue li.failed')).to_have_count(0)
        expect(self.page.locator('#lessonList li', has_text='Old exercise')).to_have_count(0)

    # ---------- lessons ----------

    def workshop(self):
        self.page.get_by_role('tab', name='Workshop').click()
        expect(self.page.locator('#lessonList li').first).to_be_visible()
        return self.page.locator('#lessonList li')

    def test_each_lesson_shows_whether_it_is_live_or_failed_its_trial_and_why(self):
        lessons = self.workshop()
        first = json.loads((REPO / 'lessons.json').read_text())[0]
        expect(lessons.filter(has_text=first['label'])).to_contain_text('Live')
        expect(lessons.filter(has_text=first['label']).get_by_role('button', name=re.compile('^Remove'))).to_have_count(0)  # its own check
        old = lessons.filter(has_text='Old exercise')
        expect(old).to_contain_text('Failed its trial: the starter does not build')
        self.pick('Asha Rao')  # a lesson still being checked is not one of their exercises yet
        expect(self.page.locator('#person')).not_to_contain_text('Old exercise')
        self.page.get_by_role('tab', name='Workshop').click()
        old.locator('summary').click()
        expect(old).to_contain_text('could not resolve org.example:retired:1.0')
        old.get_by_role('button', name='Try again').click()
        expect(self.queued()).to_have_count(2)  # removed and added again: tried again now

    def test_add_a_lesson_then_it_is_checking_then_live_and_on_the_people_tab(self):
        self.workshop()
        self.page.locator('#addLesson summary').click()
        self.page.locator('#lessonRepo').fill('https://github.com/practice/greeting')
        self.page.locator('#lessonLabel').fill('Greeting!')
        expect(self.page.locator('#lessonKey')).to_have_value('greeting')
        self.page.get_by_role('button', name='Add to changes').click()
        expect(self.queued()).to_contain_text('Add lesson Greeting! (practice/greeting, correct when its tests pass)')
        self.send()
        greeting = self.page.locator('#lessonList li', has_text='Greeting!')
        expect(greeting).to_contain_text('Checking')
        # Practice passes its trial after 3 s, as the next grading run would on GitHub; the page looks again by itself.
        expect(greeting).to_contain_text('Live', timeout=15000)
        self.pick('Asha Rao')
        expect(self.page.locator('#person')).to_contain_text('Greeting!')

    def test_adding_a_lesson_says_what_is_wrong_before_anything_is_sent(self):
        self.workshop()
        self.page.locator('#addLesson summary').click()
        first = json.loads((REPO / 'lessons.json').read_text())[0]
        self.page.locator('#lessonRepo').fill(first['repo'])
        self.page.locator('#lessonLabel').fill('Again')
        self.page.locator('#lessonKey').fill(first['key'])
        self.page.locator('#lessonCheck').select_option('tests')
        self.page.get_by_label('Tests from another repository (optional)').fill('not a repository')
        self.page.get_by_role('button', name='Add to changes').click()
        checks = self.page.locator('#lessonChecks')
        expect(checks).to_contain_text(f'The column name {first["key"]} is already used.')
        expect(checks).to_contain_text(f'{first["repo"]} is already a lesson')
        expect(checks).to_contain_text('The tests repository is owner/name/folder')
        expect(self.queued()).to_have_count(0)

    def test_tests_are_the_exercises_own_src_test_unless_another_repository_is_given(self):
        self.workshop()
        self.page.locator('#addLesson summary').click()
        other = self.page.get_by_label('Tests from another repository (optional)')
        expect(other).to_have_value('')
        self.page.locator('#lessonCheck').select_option('build')
        expect(other).to_be_hidden()  # only a tests lesson has tests to find
        self.page.locator('#lessonCheck').select_option('tests')
        expect(other).to_be_visible()

    def test_remove_a_lesson(self):
        lessons = self.workshop()
        lessons.filter(has_text='Old exercise').get_by_role('button', name='Remove lesson Old exercise').click()
        self.send()
        expect(lessons.filter(has_text='Old exercise')).to_have_count(0)

    def test_a_blocked_github_tab_keeps_the_changes(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.add_init_script('window.open = () => null')  # as a pop-up blocker does
        page.context.route('https://api.github.com/**', lambda route: route.fulfill(status=404, body='{}'))
        page.goto(self.base + '/facilitator.html?repo=someone/board#people')
        page.locator('#find').fill('Asha Rao')
        page.locator('#find').press('Enter')
        page.get_by_role('button', name='Give Asha Rao a help').click()
        page.locator('#send').click()
        expect(page.locator('#error')).to_contain_text('stopped GitHub opening')
        expect(page.locator('#error').get_by_role('button', name='Open GitHub')).to_be_visible()
        self.assertTrue(page.url.startswith(self.base), 'still on the facilitator page')
        expect(page.locator('#queue li.waiting')).to_have_count(1)

    def test_grade_now_in_practice_says_what_it_would_do(self):
        self.page.get_by_role('tab', name='Workshop').click()
        self.page.get_by_role('button', name='Grade now').click()
        expect(self.page.locator('#gradeHint')).to_contain_text('press Run workflow')

    def test_on_the_real_page_grade_now_opens_grade_submissions(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        run = {'status': 'completed', 'conclusion': 'success', 'created_at': '2026-11-16T10:00:00Z',
               'updated_at': '2026-11-16T10:05:00Z', 'html_url': 'https://github.com/someone/board/actions/runs/1'}
        page.context.route('https://github.com/**', lambda route: route.fulfill(body='GitHub', content_type='text/html'))
        page.context.route('https://api.github.com/**', lambda route: route.fulfill(
            status=200, content_type='application/json', body=json.dumps({'workflow_runs': [run]}))
            if '/actions/workflows/grade.yml/runs' in route.request.url else route.fulfill(status=404, body='{}'))
        page.goto(self.base + '/facilitator.html?repo=someone/board')  # Workshop: the default
        expect(page.locator('#gradeLast')).to_contain_text('Last graded')
        expect(page.locator('#gradeLast').get_by_role('link', name='see the run')).to_have_attribute('href', run['html_url'])
        with page.expect_popup() as popup:
            page.get_by_role('button', name='Grade now').click()
        popup.value.wait_for_url('https://github.com/someone/board/actions/workflows/grade.yml')
        expect(page.locator('#gradeHint')).to_contain_text('Run workflow')

    def test_on_the_real_page_send_opens_one_filled_in_issue_in_one_tab(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.context.route('https://github.com/**', lambda route: route.fulfill(body='GitHub', content_type='text/html'))
        page.context.route('https://api.github.com/**', lambda route: route.fulfill(status=404, body='{}'))
        page.goto(self.base + '/facilitator.html?repo=someone/board#people')
        expect(page.locator('#find')).to_be_visible()
        page.locator('#find').fill('Asha Rao')
        page.locator('#find').press('Enter')
        page.get_by_role('button', name='Give Asha Rao a help').click()
        page.get_by_role('button', name='Give Asha Rao a stretch task').click()
        with page.expect_popup() as popup:
            page.locator('#send').click()
        github = popup.value
        github.wait_for_url(re.compile(r'^https://github\.com/someone/board/issues/new\?'))
        query = dict(urllib.parse.parse_qsl(github.url.split('?', 1)[1]))
        self.assertEqual(query['template'], 'facilitator-changes.yml')
        self.assertRegex(query['batch'], r'^[A-Za-z0-9][A-Za-z0-9-]{1,63}$', 'an id leaderboard.py batch accepts')
        self.assertEqual([json.loads(line) for line in query['changes'].splitlines()],
                         [['award', 'Asha Rao', 'helped', '1'], ['award', 'Asha Rao', 'stretch', '1']])
        expect(page.locator('#queue li.waiting')).to_have_count(2)
        page.locator('#find').fill('Ben Okafor')
        page.locator('#find').press('Enter')
        page.get_by_role('button', name='Give Ben Okafor a help').click()
        page.locator('#send').click()  # a second Send: the same GitHub tab
        github.wait_for_url(re.compile(r'batch=(?!' + re.escape(query['batch']) + ')'))
        self.assertEqual(len(page.context.pages), 2)


if __name__ == '__main__':
    unittest.main()
