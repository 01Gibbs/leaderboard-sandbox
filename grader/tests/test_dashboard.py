"""dashboard.json uses the fields the page shows, and Publish the page ships every file the page loads."""
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGE = (REPO / 'index.html').read_text()


class WorkshopTests(unittest.TestCase):
    def test_the_page_shows_each_workshop_by_day_topic_and_lead(self):
        for field in ('day', 'topic', 'lead'):
            self.assertIn(f'w.{field}', PAGE)

    def test_every_workshop_in_dashboard_json_has_a_day_and_a_topic(self):
        workshops = json.loads((REPO / 'dashboard.json').read_text())['workshops']
        self.assertTrue(workshops)
        for w in workshops:
            self.assertEqual(set(w) - {'day', 'topic', 'lead'}, set(), w)
            self.assertTrue(w.get('day') and w.get('topic'), w)


class PublishedFilesTests(unittest.TestCase):
    def test_pages_publishes_every_file_the_page_loads_and_nothing_else(self):
        loaded = set(re.findall(r'<script src="([^":]+)"', PAGE)) | set(re.findall(r"_FILE = '([^']+)'", PAGE))
        copy = re.search(r'cp (.+) _site/', (REPO / '.github' / 'workflows' / 'pages.yml').read_text()).group(1)
        self.assertEqual(set(copy.split()), loaded | {'index.html'})


if __name__ == '__main__':
    unittest.main()
