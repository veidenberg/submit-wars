import unittest
from unittest import mock
import json
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from submit_wars import TogglService, ConfluenceService, process_week

class MockResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)
    
    def json(self):
        return self.json_data
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error: {self.status_code}")

class TestIntegration(unittest.TestCase):
    """Integration tests using mock API responses"""
    
    @mock.patch('requests.post')
    @mock.patch('requests.get')
    def test_process_week(self, mock_get, mock_post):
        # Mock API responses
        mock_get.return_value = MockResponse({
            "body": {"storage": {"value": "<h1>July</h1>"}},
            "title": "Weekly Reports",
            "version": {"number": 1}
        })
        
        mock_post.return_value = MockResponse([
            {"project_id": 123, "description": "Task 1"},
            {"project_id": 456, "description": "Task 2"}
        ])
        
        # Create services with mocked API calls
        with mock.patch('submit_wars.ApiService.__init__', return_value=None):
            toggl_service = TogglService(
                api_token="fake-token",
                api_url="https://api.track.toggl.com",
                workspace_id="12345",
                reports_api_url="https://api.track.toggl.com/reports"
            )
            
            # Mock fetch_projects to return test data
            toggl_service.fetch_projects = mock.MagicMock(
                return_value={123: "Project A", 456: "Project B"}
            )
            
            # Mock the fetch_time_records method
            toggl_service.fetch_time_records = mock.MagicMock(
                return_value=[
                    {"project_id": 123, "description": "Task 1"},
                    {"project_id": 456, "description": "Task 2"}
                ]
            )
            
            confluence_service = ConfluenceService(
                base_url="https://example.org",
                api_token="fake-token",
                page_id="12345",
                username="testuser"
            )
            
            # Mock the post_report method
            confluence_service.post_report = mock.MagicMock()
            
            # Test process_week function - using datetime objects instead of strings
            date_range = {
                "start_date": datetime(2023, 7, 10),
                "end_date": datetime(2023, 7, 14)
            }
            
            process_week(toggl_service, confluence_service, date_range)
            
            # Assert that post_report was called
            confluence_service.post_report.assert_called_once()
            
            # Assert that fetch_time_records was called with correct dates
            toggl_service.fetch_time_records.assert_called_once_with(
                date_range["start_date"], date_range["end_date"]
            )


if __name__ == '__main__':
    unittest.main()
