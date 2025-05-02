import unittest
from unittest import mock
from datetime import datetime, timedelta
import re
from submit_wars import (
    DateUtils, ConfluenceService, TogglService, 
    format_time_records, ApiService
)

class TestDateUtils(unittest.TestCase):
    """Test cases for DateUtils class"""
    
    def test_get_last_friday(self):
        # Test from a known Monday (2023-07-10)
        monday = datetime(2023, 7, 10)
        friday = DateUtils.get_last_friday(monday)
        self.assertEqual(friday.strftime('%Y-%m-%d'), '2023-07-07')
        
        # Test from a Friday
        friday_date = datetime(2023, 7, 7)
        prev_friday = DateUtils.get_last_friday(friday_date)
        self.assertEqual(prev_friday.strftime('%Y-%m-%d'), '2023-06-30')
        
        # Test from weekend
        sunday = datetime(2023, 7, 9)
        last_friday = DateUtils.get_last_friday(sunday)
        self.assertEqual(last_friday.strftime('%Y-%m-%d'), '2023-07-07')
    
    def test_get_last_week_dates(self):
        with mock.patch('submit_wars.DateUtils.get_last_friday') as mock_get_last_friday:
            # Set up mock to return a specific Friday
            mock_get_last_friday.return_value = datetime(2023, 7, 7)
            
            # Test the function
            date_range = DateUtils.get_last_week_dates()
            
            # Verify results
            self.assertEqual(date_range['start_date'].strftime('%Y-%m-%d'), '2023-07-03')
            self.assertEqual(date_range['end_date'].strftime('%Y-%m-%d'), '2023-07-07')
    
    def test_get_current_week_dates(self):
        with mock.patch('submit_wars.datetime') as mock_datetime:
            # Mock today as Wednesday (2023-07-12)
            mock_today = datetime(2023, 7, 12)
            mock_datetime.now.return_value = mock_today
            
            # Test function
            date_range = DateUtils.get_current_week_dates()
            
            # Should return Monday to Friday of current week
            self.assertEqual(date_range['start_date'].strftime('%Y-%m-%d'), '2023-07-10') 
            self.assertEqual(date_range['end_date'].strftime('%Y-%m-%d'), '2023-07-14')
            
            # Now test from a Friday
            mock_today = datetime(2023, 7, 14)
            mock_datetime.now.return_value = mock_today
            
            date_range = DateUtils.get_current_week_dates()
            self.assertEqual(date_range['start_date'].strftime('%Y-%m-%d'), '2023-07-10')
            self.assertEqual(date_range['end_date'].strftime('%Y-%m-%d'), '2023-07-14')
            
            # Test from a weekend (should give same week)
            mock_today = datetime(2023, 7, 15)  # Saturday
            mock_datetime.now.return_value = mock_today
            
            date_range = DateUtils.get_current_week_dates()
            self.assertEqual(date_range['start_date'].strftime('%Y-%m-%d'), '2023-07-10')
            self.assertEqual(date_range['end_date'].strftime('%Y-%m-%d'), '2023-07-15')


class TestConfluenceService(unittest.TestCase):
    """Test cases for ConfluenceService class"""
    
    def setUp(self):
        # Create a mock API service
        with mock.patch('submit_wars.ApiService.__init__', return_value=None):
            self.confluence = ConfluenceService(
                base_url="https://example.org",
                api_token="fake-token",
                page_id="12345",
                username="testuser",
                display_name="Test User"
            )
    
    def test_determine_status_message(self):
        # Test various combinations of parameters
        status = self.confluence._determine_status_message(
            month="July", 
            week_end_date="14/07", 
            user_exists=True,
            week_exists=True, 
            month_exists=True, 
            replace=True
        )
        self.assertEqual(status, "Replaced existing report for week ending 14/07.")
        
        status = self.confluence._determine_status_message(
            month="July", 
            week_end_date="14/07", 
            user_exists=True,
            week_exists=True, 
            month_exists=True, 
            replace=False
        )
        self.assertEqual(status, "Report already exists for week ending 14/07.")
        
        status = self.confluence._determine_status_message(
            month="July", 
            week_end_date="14/07", 
            user_exists=False,
            week_exists=True, 
            month_exists=True, 
            replace=False
        )
        self.assertEqual(status, "Added report to existing week ending 14/07.")
        
        status = self.confluence._determine_status_message(
            month="July", 
            week_end_date="14/07", 
            user_exists=False,
            week_exists=False, 
            month_exists=True, 
            replace=False
        )
        self.assertEqual(status, "Added new week ending 14/07.")
        
        status = self.confluence._determine_status_message(
            month="July", 
            week_end_date="14/07", 
            user_exists=False,
            week_exists=False, 
            month_exists=False, 
            replace=False
        )
        self.assertEqual(status, "Added new month 'July'.")
    
    def test_detect_date_format(self):
        # Test with unpadded dates
        content = "<h2>w/e 1/7</h2><h2>w/e 8/7</h2>"
        self.confluence._detect_date_format(content)
        self.assertEqual(self.confluence.date_format, "unpadded")
        
        # Test with padded dates
        self.confluence.date_format = None
        content = "<h2>w/e 01/07</h2><h2>w/e 08/07</h2>"
        self.confluence._detect_date_format(content)
        self.assertEqual(self.confluence.date_format, "padded")
        
        # Test with no dates (should default to padded)
        self.confluence.date_format = None
        content = "<h1>July</h1><p>Some content</p>"
        self.confluence._detect_date_format(content)
        self.assertEqual(self.confluence.date_format, "padded")


class TestFormatting(unittest.TestCase):
    """Test cases for formatting functions"""
    
    def test_format_time_records(self):
        # Test with empty records
        result = format_time_records([], {})
        self.assertEqual(result, "No time records found for the last week.")
        
        # Test with actual records
        time_records = [
            {"project_id": 123, "description": "Task 1"},
            {"project_id": 123, "description": "Task 2"},
            {"project_id": 456, "description": "Another task"},
            {"project_id": None, "description": "No project task"},
        ]
        project_map = {123: "Project A", 456: "Project B"}
        
        result = format_time_records(time_records, project_map)
        
        # Check that all projects appear in the output
        self.assertIn("Project A", result)
        self.assertIn("Project B", result)
        self.assertIn("Other", result)
        
        # Check that all tasks appear in the output
        self.assertIn("Task 1", result)
        self.assertIn("Task 2", result)
        self.assertIn("Another task", result)
        self.assertIn("No project task", result)
        
        # Verify HTML structure
        self.assertTrue(result.startswith("<ul>"))
        self.assertTrue(result.endswith("</ul>"))


if __name__ == '__main__':
    unittest.main()
