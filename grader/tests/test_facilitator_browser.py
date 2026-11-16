"""End to end: the facilitator page in a real browser, on facilitator_walkthrough.py's practice copy.

A facilitator's journey through every form: type a person, press Save, see Done or Not changed, and the sheet
changes (or doesn't). Slow tier. Needs Playwright with Chromium:
    uv run --no-project --with playwright python -m playwright install chromium
    uv run --no-project --with playwright python -m unittest grader/tests/test_facilitator_browser.py
It skips when Playwright or its browser is missing.
"""
import csv
import io
import re
import shutil
import sys
import threading
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
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.answer = True  # how confirm() dialogs are answered
        self.page.on('dialog', lambda d: d.accept() if self.answer else d.dismiss())
        self.page.goto(self.base + '/facilitator.html?practice')
        expect(self.page.locator('#who')).to_have_text('Practising')

    def tearDown(self):
        self.assertEqual(self.errors, [], 'JavaScript errors on the page')

    # ---------- helpers ----------

    def form(self, form_id):
        return self.page.locator(f'[data-tour="form-{form_id}"]')

    def fill(self, form_id, **values):
        f = self.form(form_id)
        for name, value in values.items():
            field = f.locator(f'[name="{name}"]')
            if field.evaluate('e => e.tagName') == 'SELECT':
                field.select_option(value)
            else:
                field.fill(value)
        return f

    def save(self, form_id, **values):
        """Fill in and send a form; returns the line it adds under "Started from this page" once finished."""
        before = self.page.locator('#runs li').count()
        self.fill(form_id, **values).locator('button[type=submit]').click()
        item = self.page.locator('#runs li').first
        expect(self.page.locator('#runs li')).to_have_count(before + 1)
        expect(item).to_have_class(re.compile(r'\b(ok|bad)\b'), timeout=15000)  # Done or Not changed
        return item

    def sheet(self):
        with urllib.request.urlopen(self.base + '/participants.csv') as r:
            return {row['name']: row for row in csv.DictReader(io.StringIO(r.read().decode()))}

    # ---------- the journeys ----------

    def test_award_says_what_it_will_do_then_does_it(self):
        helped = int(self.sheet()['Asha Rao']['helped'] or 0)
        self.fill('award', person='Asha Rao', kind='helped', amount='2')
        expect(self.form('award').locator('.preview')).to_have_text('Give 2 helps to Asha Rao.')
        item = self.save('award', person='Asha Rao', kind='helped', amount='2')
        expect(item).to_have_class('ok')
        expect(item).to_contain_text('Gave 2 helps to Asha Rao')
        self.assertEqual(int(self.sheet()['Asha Rao']['helped']), helped + 2)
        expect(self.page.locator('#history li').first).to_contain_text('Gave 2 helps to Asha Rao')

    def test_taking_points_away(self):
        self.fill('award', person='Ben Okafor', kind='stretch', amount='-1')
        expect(self.form('award').locator('.preview')).to_have_text('Take 1 stretch task from Ben Okafor.')
        expect(self.save('award', person='Ben Okafor', kind='stretch', amount='-1')).to_have_class('ok')
        self.assertEqual(int(self.sheet()['Ben Okafor']['stretch'] or 0), 0)

    def test_mark_uses_the_exercise_list_and_refuses_to_go_below_a_graded_result(self):
        lesson = self.form('mark').locator('select[name=lesson] option').nth(1).get_attribute('value')
        expect(self.save('mark', person='Ben Okafor', lesson=lesson, status='correct')).to_have_class('ok')
        self.assertEqual(self.sheet()['Ben Okafor'][lesson], 'correct')
        # Asha's pull request on the first lesson passed (the practice copy's results), so lowering it is refused.
        item = self.save('mark', person='Asha Rao', lesson=lesson, status='none')
        expect(item).to_have_class('bad')
        expect(item).to_contain_text('graded correct')
        self.assertEqual(self.sheet()['Asha Rao'][lesson], 'correct')

    def test_add_rename_merge_and_undo_them_all(self):
        start = self.sheet()
        expect(self.save('add', name='Zoe Test', github='zoetest')).to_have_class('ok')
        expect(self.page.locator('#people option[value="Zoe Test"]')).to_have_count(1)  # the pickers know her now
        expect(self.save('rename', person='zoetest', new_name='Zoe T')).to_have_class('ok')
        expect(self.save('add', name='Zoe Again', github='zoe-alt')).to_have_class('ok')
        expect(self.save('merge', keep='Zoe T', duplicate='Zoe Again')).to_have_class('ok')
        sheet = self.sheet()
        self.assertEqual(sheet['Zoe T']['github_username'], 'zoetest zoe-alt')
        self.assertNotIn('Zoe Again', sheet)
        for _ in range(4):
            expect(self.save('undo')).to_have_class('ok')
        self.assertEqual(self.sheet(), start)
        expect(self.page.locator('#history li')).to_have_text(['No facilitator changes yet.'])

    def test_a_name_not_on_the_board_asks_first_and_cancelling_sends_nothing(self):
        self.answer = False
        self.fill('award', person='Nobody Here').locator('button[type=submit]').click()
        expect(self.page.locator('#noRuns')).to_be_visible()
        self.answer = True
        item = self.save('award', person='Nobody Here')
        expect(item).to_have_class('bad')
        expect(item).to_contain_text('Nobody called "Nobody Here"')

    def test_on_the_real_page_save_opens_the_filled_in_issue_on_github(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.route('https://github.com/**', lambda route: route.fulfill(body='GitHub'))  # never leave this computer
        page.route('https://api.github.com/**', lambda route: route.fulfill(status=404, body='{}'))
        page.goto(self.base + '/facilitator.html?repo=someone/board')
        expect(page.locator('#how')).to_be_visible()
        form = page.locator('[data-tour="form-award"]')
        form.locator('[name=person]').fill('Asha Rao')
        form.locator('[name=amount]').fill('2')
        expect(form.get_by_role('link', name='or run it in Actions')).to_have_attribute(
            'href', 'https://github.com/someone/board/actions/workflows/facilitator-award.yml')
        with page.expect_popup() as popup:
            form.locator('button[type=submit]').click()
        url = popup.value.url
        self.assertTrue(url.startswith('https://github.com/someone/board/issues/new?'), url)
        query = dict(urllib.parse.parse_qsl(url.split('?', 1)[1]))
        self.assertEqual(query, {'template': 'facilitator-award.yml', 'person': 'Asha Rao', 'kind': 'helped', 'amount': '2'})
        expect(page.locator('#runs li').first).to_contain_text('Opened on GitHub')


if __name__ == '__main__':
    unittest.main()
