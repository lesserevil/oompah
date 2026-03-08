import unittest
from oompah.issue_detail_api import get_issue_detail

class TestIssueDetailAPI(unittest.TestCase):
    def test_get_issue_detail(self):
        # Test that the API returns the correct issue detail
        issue_detail = get_issue_detail(1)
        self.assertEqual(issue_detail['id'], 1)
        self.assertEqual(issue_detail['title'], 'Test Issue')
        self.assertEqual(issue_detail['description'], 'This is a test issue')
