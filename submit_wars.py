#!/usr/bin/env python3

import os
import sys
import json
import base64
import re
import argparse
import logging
from datetime import datetime, timedelta
import requests
from pathlib import Path
from dotenv import load_dotenv

# ============================================================================
# CONFIGURATION
# ============================================================================

def load_config():
    """Load configuration from environment variables"""
    # Find and load .env file
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)

    # Check if running in verbose mode
    is_verbose = '--verbose' in sys.argv

    # Set up logger
    log_level = logging.DEBUG if is_verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(message)s'
    )

    # Create config dict
    config = {
        'toggl': {
            'api_token': os.getenv('TOGGL_API_TOKEN'),
            'workspace_id': os.getenv('TOGGL_WORKSPACE_ID'),
            'api_url': 'https://api.track.toggl.com/api/v9',
            'report_api_url': 'https://api.track.toggl.com/reports/api/v2',
        },
        'confluence': {
            'username': os.getenv('CONFLUENCE_USERNAME'),
            'api_token': os.getenv('CONFLUENCE_API_TOKEN'),
            'space_key': os.getenv('CONFLUENCE_SPACE_KEY'),
            'page_id': os.getenv('CONFLUENCE_PAGE_ID'),
            'base_url': os.getenv('CONFLUENCE_BASE_URL'),
            'display_name': os.getenv('CONFLUENCE_DISPLAY_NAME') or os.getenv('CONFLUENCE_USERNAME') or 'Andres',
        },
        'app': {
            'debug': is_verbose,
        }
    }

    return config

# ============================================================================
# DATE UTILITIES
# ============================================================================

class DateUtils:
    """Centralized date handling utilities"""
    
    @staticmethod
    def get_last_friday(from_date=None):
        """Get the most recent Friday from a given date"""
        date = from_date or datetime.now()
        day_of_week = date.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday
        
        if day_of_week == 5:  # Saturday
            last_friday = date - timedelta(days=1)
        elif day_of_week == 6:  # Sunday
            last_friday = date - timedelta(days=2)
        else:  # Monday through Friday
            last_friday = date - timedelta(days=day_of_week + 3)
        
        return last_friday
    
    @staticmethod
    def get_last_week_dates():
        """Gets the date range for the last full work week (Monday through Friday)"""
        # Calculate the most recent Friday
        last_friday = DateUtils.get_last_friday()
        
        # Set to end of Friday (23:59:59)
        last_friday = last_friday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Calculate Monday of that week (4 days before Friday)
        monday_of_last_week = last_friday - timedelta(days=4)
        monday_of_last_week = monday_of_last_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        logging.debug(f"Last full work week: {monday_of_last_week.strftime('%Y-%m-%d')} to {last_friday.strftime('%Y-%m-%d')}")
        
        return {
            'start_date': monday_of_last_week,
            'end_date': last_friday
        }
    
    @staticmethod
    def get_all_weeks_in_year(year=None):
        """Gets all weeks in the specified year (or current year if not specified), from January 1st to current date"""
        weeks = []
        today = datetime.now()
        
        # Use specified year or current year
        current_year = year if year is not None else today.year
        
        # Start from first day of the year
        start_date = datetime(current_year, 1, 1, 0, 0, 0)
        
        # Find the first Friday
        current_date = start_date
        day_of_week = current_date.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday
        
        # If not already a Friday (4), move to the first Friday
        if day_of_week != 4:  # 4 = Friday
            current_date += timedelta(days=((4 - day_of_week) % 7))
        
        # Set to end of day for Fridays
        current_date = current_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # For past years, go through all Fridays of the year
        # For current year, only go up to the current date
        end_date = datetime(current_year, 12, 31, 23, 59, 59, 999999) if current_year < today.year else today
        
        # Keep generating weeks until we reach the end date
        while current_date <= end_date:
            # Create the week
            week_end_date = current_date
            week_start_date = week_end_date - timedelta(days=4)  # Monday is 4 days before Friday
            week_start_date = week_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            weeks.append({
                'start_date': week_start_date,
                'end_date': week_end_date
            })
            
            # Move to next Friday
            current_date += timedelta(days=7)
        
        logging.debug(f"Generated {len(weeks)} weeks for {current_year}")
        
        return weeks
    
    @staticmethod
    def get_week_info_from_date(date=None):
        """Get month name and week ending date from a date"""
        date = date or DateUtils.get_last_friday()
        
        return {
            'month': date.strftime('%B'),
            'week_end_date': date.strftime('%d/%m')
        }

# ============================================================================
# API SERVICE
# ============================================================================

class ApiService:
    """Base API service with common methods"""
    
    def __init__(self, base_url, api_token):
        self.base_url = base_url
        self.api_token = api_token
    
    def make_request(self, method, endpoint, data=None, headers=None):
        """Make an HTTP request to the API with error handling"""
        url = f"{self.base_url}{endpoint}"
        headers = headers or {}
        
        logging.debug(f"{method} request: {url}")
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Error in {method} request to {url}: {str(e)}")
            raise
    
    def get(self, endpoint, headers=None):
        """Make a GET request to the API"""
        return self.make_request('GET', endpoint, headers=headers)
    
    def put(self, endpoint, data, headers=None):
        """Make a PUT request to the API"""
        return self.make_request('PUT', endpoint, data=data, headers=headers)
    
    def post(self, endpoint, data, headers=None):
        """Make a POST request to the API"""
        return self.make_request('POST', endpoint, data=data, headers=headers)

# ============================================================================
# TOGGL SERVICE
# ============================================================================

class TogglService(ApiService):
    """Service for interacting with the Toggl API"""
    
    def __init__(self, api_token, api_url, workspace_id):
        super().__init__(api_url, api_token)
        self.workspace_id = workspace_id
        self.earliest_allowed_date = None
        
        # Validate required fields
        if not api_token:
            logging.error("Toggl API token is missing")
        if not workspace_id:
            logging.error("Toggl workspace ID is missing")
    
    def get_toggl_headers(self):
        """Create headers for Toggl API authentication"""
        auth_token = base64.b64encode(f"{self.api_token}:api_token".encode()).decode()
        return {
            'Authorization': f"Basic {auth_token}",
            'Content-Type': 'application/json'
        }
    
    def fetch_time_records(self, start_date, end_date):
        """Fetch time records from Toggl API"""
        # Adjust dates if needed
        start_date, end_date = self._adjust_date_range(start_date, end_date)
        
        if start_date >= end_date:
            logging.debug("Start date is after end date after adjustments")
            return []

        # Format dates using YYYY-MM-DD format for API request
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        endpoint = f"/me/time_entries?start_date={start_date_str}&end_date={end_date_str}"
        
        try:
            time_records = self.get(endpoint, self.get_toggl_headers())
            logging.debug(f"Retrieved {len(time_records)} time entries from Toggl")
            return time_records
        except Exception as e:
            error_message = str(e)
            
            # Check if this is the "start_date must not be earlier than" error
            if "start_date must not be earlier than" in error_message:
                date_match = re.search(r"than (\d{4}-\d{2}-\d{2})", error_message)
                if date_match and date_match.group(1):
                    # Extract the earliest allowed date and store it
                    earliest_date = datetime.fromisoformat(date_match.group(1))
                    self.earliest_allowed_date = earliest_date
                    
                    logging.debug(f"Toggl API restriction: earliest allowed date is {earliest_date.isoformat()}")
                    logging.debug("Retrying with adjusted start date")
                    
                    # Try again with the corrected start date
                    return self.fetch_time_records(earliest_date, end_date)
            
            raise Exception(f"Failed to fetch time records: {error_message}")
    
    def _adjust_date_range(self, start_date, end_date):
        """Adjust date range based on API limitations and current time"""
        # Check if start_date is earlier than earliest allowed date
        if self.earliest_allowed_date and start_date < self.earliest_allowed_date:
            logging.debug(f"Start date {start_date.isoformat()} is earlier than the earliest allowed date {self.earliest_allowed_date.isoformat()}")
            start_date = self.earliest_allowed_date
        
        # Check if dates are in the future
        current_time = datetime.now()
        if start_date > current_time:
            logging.debug(f"Start date {start_date.isoformat()} is in the future, adjusting to current time")
            start_date = current_time
        
        if end_date > current_time:
            logging.debug(f"End date {end_date.isoformat()} is in the future, adjusting to current time")
            end_date = current_time
            
        return start_date, end_date
    
    def fetch_projects(self):
        """Fetch projects from Toggl API"""
        # Check if workspace_id exists before making the API call
        if not self.workspace_id:
            logging.error("Cannot fetch projects: Workspace ID is missing")
            return {}
        
        endpoint = f"/workspaces/{self.workspace_id}/projects"
        
        logging.debug(f"Fetching projects from: {self.base_url}{endpoint}")
        
        try:
            projects = self.get(endpoint, self.get_toggl_headers())
            logging.debug(f"Retrieved {len(projects)} projects from Toggl")
            
            project_map = {project['id']: project['name'] for project in projects}
            return project_map
        except Exception as e:
            logging.error(f"Error fetching projects from Toggl: {str(e)}")
            raise

# ============================================================================
# CONFLUENCE SERVICE
# ============================================================================

class ConfluenceService(ApiService):
    """Service for interacting with the Confluence API"""
    
    def __init__(self, base_url, api_token, space_key, page_id, username, display_name=None):
        super().__init__(base_url, api_token)
        self.space_key = space_key
        self.page_id = page_id
        self.username = username
        self.display_name = display_name or username or 'Andres'
        self.month_names = ["January", "February", "March", "April", "May", "June", 
                           "July", "August", "September", "October", "November", "December"]
    
    def get_existing_content(self):
        """Retrieves the existing page content for analysis"""
        page_data = self.get_page_content()
        return page_data['content']
    
    def has_week_for_user(self, content, week_end_date):
        """Checks if a specific week already has content for the current user"""
        # Check for user heading under this week (h3 with display name)
        user_heading_pattern = re.compile(f'<h2>w/e {week_end_date}</h2>.*?<h3>{self.display_name}</h3>', re.DOTALL)
        return bool(user_heading_pattern.search(content))
    
    def post_report(self, formatted_content, date_range=None):
        """Post a report to Confluence"""
        logging.debug("Creating Confluence content")
        
        # Get current page content first
        current_page_data = self.get_page_content()
        
        # Use provided date range or use current dates
        if date_range:
            # Extract month and date from the provided date range
            week_info = DateUtils.get_week_info_from_date(date_range['end_date'])
        else:
            week_info = DateUtils.get_week_info_from_date()
        
        # Prepare the new content and get status information
        updated_content, status = self.prepare_updated_content(
            current_page_data['content'],
            formatted_content,
            week_info
        )
        
        # Only update if content has changed
        if updated_content != current_page_data['content']:
            self.save_page(current_page_data['title'], updated_content, current_page_data['version'])
            logging.info(status)
        else:
            logging.info(status)
    
    def get_page_content(self):
        """Get the content of a Confluence page"""
        endpoint = f"/rest/api/content/{self.page_id}?expand=body.storage,version"
        logging.debug("Fetching current page content")
        
        try:
            response = self.get(endpoint, {
                'Authorization': f"Bearer {self.api_token}"
            })
            
            return {
                'content': response['body']['storage']['value'],
                'title': response['title'],
                'version': response['version']['number']
            }
        except Exception as e:
            logging.error(f"Error fetching page content: {str(e)}")
            raise
    
    def save_page(self, title, content, current_version):
        """Save content to a Confluence page"""
        endpoint = f"/rest/api/content/{self.page_id}"
        logging.debug("Updating Confluence page")
        
        try:
            payload = {
                'version': {'number': current_version + 1},
                'title': title,
                'type': 'page',
                'body': {
                    'storage': {
                        'value': content,
                        'representation': 'storage'
                    }
                }
            }
            
            response = self.put(endpoint, payload, {
                'Authorization': f"Bearer {self.api_token}"
            })
            logging.debug(f"Confluence update response status: {'success' if response else 'failure'}")
        except Exception as e:
            logging.error(f"Error updating Confluence page: {str(e)}")
            raise
    
    def prepare_updated_content(self, current_content, formatted_content, week_info):
        """Prepare the updated content for the Confluence page"""
        # Get week identifier and user info
        month = week_info['month']
        week_end_date = week_info['week_end_date']
        display_name = self.display_name
        
        # Define patterns for checking existing content
        month_heading_pattern = re.compile(f'<h1>{month}</h1>', re.IGNORECASE)
        week_heading_pattern = re.compile(f'<h2>w/e {week_end_date}</h2>', re.IGNORECASE)
        user_heading_pattern = re.compile(f'<h2>w/e {week_end_date}</h2>.*?<h3>{display_name}</h3>', re.DOTALL)
        
        logging.debug(f"Checking for month: {month}")
        logging.debug(f"Checking for week: w/e {week_end_date}")
        logging.debug(f"Checking for user: {display_name}")
        
        # Case 1: This user's report already exists for this week
        if user_heading_pattern.search(current_content):
            logging.debug("This user already has a report for this week")
            return current_content, f"Report already exists for week ending {week_end_date}."
        
        # Completely reorganize the page in proper chronological order
        logging.debug("Processing content to maintain chronological order")
        
        # Extract all existing month sections
        month_sections = self.extract_month_sections(current_content)
        
        # Add our new content to the appropriate section
        updated_sections = self.add_content_to_month_sections(
            month_sections, month, week_end_date, display_name, formatted_content
        )
        
        # Reorder all sections and regenerate the entire page content
        ordered_content = self.regenerate_ordered_content(updated_sections)
        
        # Determine the appropriate status message
        if user_heading_pattern.search(current_content):
            status = f"Report already exists for week ending {week_end_date}."
        elif week_heading_pattern.search(current_content):
            status = f"Added report to existing week ending {week_end_date}."
        elif month_heading_pattern.search(current_content):
            status = f"Added new week ending {week_end_date}."
        else:
            status = f"Added new month '{month}'."
        
        return ordered_content, status
    
    def extract_month_sections(self, content):
        """Extracts all month sections from the content"""
        month_sections = {}
        
        # Extract each month section
        month_pattern = re.compile(r'<h1>([A-Za-z]+)</h1>([\s\S]*?)(?=<h1>|$)')
        
        for match in month_pattern.finditer(content):
            month_name = match.group(1)
            month_content = match.group(0)
            
            if month_name in self.month_names:
                month_sections[month_name] = month_content
                logging.debug(f"Found existing month section: {month_name}")
        
        return month_sections
    
    def _parse_week_date(self, week_end_date):
        """Parse the date from a week ending string (DD/MM)"""
        day, month = map(int, week_end_date.split('/'))
        return datetime.now().replace(day=day, month=month)
    
    def add_content_to_month_sections(self, sections, month, week_end_date, display_name, formatted_content):
        """Adds the new content to the appropriate month section"""
        # Clone the sections dictionary
        updated_sections = sections.copy()
        
        # Check if the month already exists
        if month in updated_sections:
            month_content = updated_sections[month]
            
            # Check if week exists in this month
            week_pattern = re.compile(f'<h2>w/e {week_end_date}</h2>', re.IGNORECASE)
            week_exists = bool(week_pattern.search(month_content))
            
            # Check if user exists for this week
            user_pattern = re.compile(f'<h2>w/e {week_end_date}</h2>.*?<h3>{display_name}</h3>', re.DOTALL)
            user_exists = bool(user_pattern.search(month_content))
            
            if user_exists:
                # No changes needed
                logging.debug(f"User {display_name} already exists for week ending {week_end_date}")
                return updated_sections
            elif week_exists:
                # Add user to existing week
                updated_sections[month] = self._add_user_to_existing_week(
                    month_content, week_pattern, display_name, formatted_content
                )
            else:
                # Add new week to existing month
                updated_sections[month] = self._add_new_week_to_existing_month(
                    month_content, month, week_end_date, display_name, formatted_content
                )
        else:
            # Create a new month section
            logging.debug(f"Creating new month section for {month}")
            new_section = self._create_full_section(month, week_end_date, display_name, formatted_content)
            updated_sections[month] = new_section
        
        return updated_sections
    
    def _add_user_to_existing_week(self, month_content, week_pattern, display_name, formatted_content):
        """Add a user section to an existing week"""
        logging.debug(f"Adding user to existing week")
                
        # Split content at the week heading
        parts = week_pattern.split(month_content)
        if len(parts) < 2:
            logging.debug("Week pattern found but couldn't split content properly")
            return month_content
        
        # Find where to insert the user section
        after_week_heading = parts[1]
        next_heading_match = re.search(r'<h[123][^>]*>', after_week_heading, re.IGNORECASE)
        
        # Extract week end date safely
        week_end_date = ""
        try:
            pattern_str = week_pattern.pattern
            if 'w/e ' in pattern_str and '</h2>' in pattern_str:
                week_end_date = pattern_str.split('w/e ')[1].split('</h2>')[0]
        except Exception:
            logging.debug("Could not extract week end date from pattern")
        
        if next_heading_match:
            # Insert user section before the next heading
            insert_point = next_heading_match.start()
            user_section = self._create_user_section(display_name, formatted_content)
            
            return parts[0] + \
                   f"<h2>w/e {week_end_date}</h2>" + \
                   after_week_heading[:insert_point] + \
                   user_section + \
                   after_week_heading[insert_point:]
        else:
            # No next heading, append to the end of the week section
            user_section = self._create_user_section(display_name, formatted_content)
            return parts[0] + \
                   f"<h2>w/e {week_end_date}</h2>" + \
                   after_week_heading + user_section
    
    def _add_new_week_to_existing_month(self, month_content, month, week_end_date, display_name, formatted_content):
        """Add a new week to an existing month section"""
        logging.debug(f"Adding new week to existing month {month}")
        
        # Extract all week headings in this month to determine where to insert
        week_headings = []
        week_heading_regex = re.compile(r'<h2>w\/e (\d{2})\/(\d{2})<\/h2>')
        
        for week_match in week_heading_regex.finditer(month_content):
            try:
                day = int(week_match.group(1))
                month_num = int(week_match.group(2)) - 1  # Python months are 0-indexed
                
                # Create a date object for this week
                date = datetime.now().replace(day=day, month=month_num+1)
                
                week_headings.append({
                    'date': date,
                    'index': week_match.start()
                })
            except Exception:
                logging.debug(f"Could not parse date: {week_match.group(1)}, {week_match.group(2)}")
        
        # Parse the new week date
        new_date = self._parse_week_date(week_end_date)
        
        # Create the week section to insert
        week_section = self._create_week_section(week_end_date, display_name, formatted_content)
        
        # Add after the h1 by default
        h1_end_index = month_content.find('</h1>') + 5
        insert_position = h1_end_index
        
        # Sort weeks by date in reverse chronological order (newest first)
        week_headings.sort(key=lambda x: x['date'].timestamp(), reverse=True)
        
        # Find where to insert the new week to maintain reverse chronological order
        inserted = False
        for i, heading in enumerate(week_headings):
            # If current week is older than our new week, insert before it
            if heading['date'] < new_date:
                insert_position = heading['index']
                inserted = True
                logging.debug(f"Adding week ending {week_end_date} before week at index {heading['index']}")
                break
            
            # If we're at the last heading and haven't inserted yet, 
            # our new week is the oldest, so append after the last week
            if i == len(week_headings) - 1 and not inserted:
                next_heading_match = re.search(r'<h[12][^>]*>', month_content[heading['index'] + 20:], re.IGNORECASE)
                if next_heading_match:
                    insert_position = heading['index'] + 20 + next_heading_match.start()
                else:
                    # No next heading, append at the end of month content
                    insert_position = len(month_content)
                logging.debug(f"Adding week ending {week_end_date} at the end of month section")
        
        # If no weeks exist yet, insert right after h1
        if not week_headings:
            logging.debug(f"No existing weeks in month, adding after h1")
        
        return month_content[:insert_position] + week_section + month_content[insert_position:]
    
    def regenerate_ordered_content(self, sections):
        """Regenerates the content with all months in the correct order"""
        # Sort the sections by month (reverse chronological order)
        months = list(sections.keys())
        months.sort(key=lambda m: self.month_names.index(m), reverse=True)
        
        # Construct the page content with months in the correct order
        ordered_content = ''
        for month in months:
            ordered_content += sections[month]
        
        return ordered_content
    
    def _create_html_section(self, tag, content, attributes=None):
        """Create an HTML section with specified tag and content"""
        attr_str = ""
        if attributes:
            attr_str = " " + " ".join([f'{k}="{v}"' for k, v in attributes.items()])
        
        return f"<{tag}{attr_str}>{content}</{tag}>"
    
    def _create_full_section(self, month, week_end_date, display_name, formatted_content):
        """Create a full section with month, week, and user content"""
        return f"""
<h1>{month}</h1>
<h2>w/e {week_end_date}</h2>
<h3>{display_name}</h3>
{formatted_content}
"""
    
    def _create_week_section(self, week_end_date, display_name, formatted_content):
        """Create a section for a week with user content"""
        return f"""
<h2>w/e {week_end_date}</h2>
<h3>{display_name}</h3>
{formatted_content}
"""
    
    def _create_user_section(self, display_name, formatted_content):
        """Create a section for a user"""
        return f"""
<h3>{display_name}</h3>
{formatted_content}
"""

# ============================================================================
# FORMATTING UTILITIES
# ============================================================================

def format_time_records(time_records, project_map):
    """Format time records into HTML for Confluence"""
    logging.debug(f"Formatting {len(time_records)} time records")
    
    if not time_records:
        logging.debug("No time records found")
        return "No time records found for the last week."
    
    project_groups = {}
    
    for record in time_records:
        project_id = record.get('pid')
        project_name = project_map.get(project_id, 'No Project') if project_id else 'No Project'
        
        if project_name not in project_groups:
            project_groups[project_name] = set()
        
        description = record.get('description', '').strip()
        if description:
            project_groups[project_name].add(description)
    
    formatted_output = '<ul>'
    sorted_projects = sorted(project_groups.keys())
    
    for project_name in sorted_projects:
        formatted_output += f"<li>{project_name}"
        
        tasks = sorted(project_groups[project_name])
        if tasks:
            formatted_output += '<ul>'
            for task in tasks:
                formatted_output += f"<li>{task}</li>"
            formatted_output += '</ul>'
        
        formatted_output += '</li>'
    
    formatted_output += '</ul>'
    
    return formatted_output

# ============================================================================
# MAIN APPLICATION LOGIC
# ============================================================================

def validate_env_vars(config):
    """Validate required environment variables"""
    required_env_vars = [
        {'value': config['toggl']['api_token'], 'name': 'TOGGL_API_TOKEN'},
        {'value': config['toggl']['workspace_id'], 'name': 'TOGGL_WORKSPACE_ID'},
        {'value': config['confluence']['username'], 'name': 'CONFLUENCE_USERNAME'},
        {'value': config['confluence']['api_token'], 'name': 'CONFLUENCE_API_TOKEN'},
        {'value': config['confluence']['base_url'], 'name': 'CONFLUENCE_BASE_URL'}
    ]
    
    missing_vars = [env_var['name'] for env_var in required_env_vars if not env_var['value']]
    
    if missing_vars:
        for var_name in missing_vars:
            logging.error(f"ERROR: {var_name} is not set in environment variables")
        sys.exit(1)

def process_week(toggl_service, confluence_service, date_range, existing_project_map=None):
    """Process a single week and post to Confluence"""
    week_date_str = date_range['end_date'].strftime('%d/%m')
    logging.debug(f"Fetching time records for week ending {week_date_str}...")
    
    # Only fetch project map if not provided
    project_map = existing_project_map or toggl_service.fetch_projects()
    
    time_records = toggl_service.fetch_time_records(date_range['start_date'], date_range['end_date'])
    logging.info(f"Retrieved {len(time_records)} time entries")
    
    if not time_records:
        raise Exception("No time records found for this period")
    
    # Show sample time record in debug mode
    if time_records and logging.getLogger().level == logging.DEBUG:
        logging.debug(f"Sample time record: {json.dumps(time_records[0:1])}")
    
    formatted_report = format_time_records(time_records, project_map)
    
    logging.debug(f"Posting report for week ending {week_date_str} to Confluence...")
    confluence_service.post_report(formatted_report, date_range)

def fill_in_missing_weeks(toggl_service, confluence_service, year=None):
    """Fill in reports for all missing weeks in the specified year"""
    # Get all weeks in the year
    all_weeks = DateUtils.get_all_weeks_in_year(year)
    logging.info(f"Found {len(all_weeks)} weeks in year {year or datetime.now().year} to process.")
    
    # Get the existing content to check which weeks are already reported
    existing_content = confluence_service.get_existing_content()
    
    # Fetch project map once at the beginning
    project_map = toggl_service.fetch_projects()
    logging.debug("Project map fetched")
    
    stats = {
        'processed': 0,
        'skipped': 0,
        'errors': 0,
        'no_data': 0
    }
    
    # Process each week in reverse order (newest first)
    # This ensures we discover the earliest allowed date first
    reversed_weeks = all_weeks.copy()
    reversed_weeks.reverse()
    
    for i, week in enumerate(reversed_weeks):
        week_end_date_str = week['end_date'].strftime('%d/%m')
        
        week_index = len(all_weeks) - i
        logging.info(f"[{week_index}/{len(all_weeks)}] Week ending {week_end_date_str}")
        
        # Check if this week already exists for this user
        if confluence_service.has_week_for_user(existing_content, week_end_date_str):
            logging.info(f"✓ Already exists. Skipping.")
            stats['skipped'] += 1
            continue
        
        logging.debug(f"Processing week ending {week_end_date_str}...")
        try:
            # Pass project_map to process_week
            process_week(toggl_service, confluence_service, week, project_map)
            stats['processed'] += 1
            # Add a delay to avoid API rate limits
            if i < len(reversed_weeks) - 1:
                logging.debug("Waiting before processing next week...")
                import time
                time.sleep(2)
        except Exception as e:
            if "No time records found" in str(e):
                logging.info(f"ℹ No time entries found for this week. Skipping.")
                stats['no_data'] += 1
            else:
                logging.error(f"✗ Error: {str(e)}")
                stats['errors'] += 1
            # Continue with the next week even if this one fails
    
    print_summary(stats, len(all_weeks))

def print_summary(stats, total_weeks):
    """Print a summary of the processing results"""
    logging.info("\n===== Summary =====")
    logging.info(f"Total weeks found: {total_weeks}")
    logging.info(f"Weeks successfully processed: {stats['processed']}")
    logging.info(f"Weeks skipped (already existed): {stats['skipped']}")
    logging.info(f"Weeks with no time data: {stats['no_data']}")
    logging.info(f"Weeks with errors: {stats['errors']}")

def main():
    """Main application entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Toggl to Confluence Report Generator')
    parser.add_argument('--fill-all-weeks', action='store_true', help='Fill in all missing weeks in the current year')
    parser.add_argument('--year', type=int, help='Specify the year to process (default: current year)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    
    # Process the year argument
    year = args.year
    
    if args.verbose:
        logging.debug(f"Command line args: {vars(args)}")
        logging.debug("Running in verbose mode")
        logging.debug(f"Fill-in mode enabled: {args.fill_all_weeks}")
        if year:
            logging.debug(f"Processing year: {year}")
    
    # Validate environment variables
    validate_env_vars(config)
    
    # Initialize services
    toggl_service = TogglService(
        config['toggl']['api_token'] or '',
        config['toggl']['api_url'],
        config['toggl']['workspace_id'] or ''
    )
    
    confluence_service = ConfluenceService(
        config['confluence']['base_url'] or '',
        config['confluence']['api_token'] or '',
        config['confluence']['space_key'] or '',
        config['confluence']['page_id'] or '',
        config['confluence']['username'] or 'Andres',
        config['confluence']['display_name']
    )
    
    try:
        if args.fill_all_weeks:
            year_msg = f" for {year}" if year else ""
            logging.info(f"Fill-in mode activated. Will attempt to add reports for all missing weeks{year_msg}.")
            fill_in_missing_weeks(toggl_service, confluence_service, year)
        else:
            # Regular mode - just process the most recent week
            logging.info("Processing the most recent week...")
            process_week(toggl_service, confluence_service, DateUtils.get_last_week_dates())
        
        logging.info("All operations completed successfully!")
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        if config['app']['debug']:
            import traceback
            logging.error(f"Full error details:")
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()