#!/usr/bin/env python3

import html
import os
import sys
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

    # Set up logger
    is_verbose = '--verbose' in sys.argv
    log_level = logging.DEBUG if is_verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(message)s')

    # Create config dict
    config = {
        'toggl': {
            'api_token': os.getenv('TOGGL_API_TOKEN'),
            'workspace_id': os.getenv('TOGGL_WORKSPACE_ID'),
            'api_url': 'https://api.track.toggl.com/api/v9',
            'reports_api_url': 'https://api.track.toggl.com/reports/api/v3',
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
        
        # Days to subtract to get to the last Friday
        days_delta = (day_of_week + 3) % 7 or 7  # 0 means we're on Friday, so use 7
        
        return date - timedelta(days=days_delta)
    
    @staticmethod
    def get_last_week_dates():
        """Gets the date range for the last full work week (Monday through Friday)"""
        last_friday = DateUtils.get_last_friday()
        last_friday = last_friday.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        monday_of_last_week = last_friday - timedelta(days=4)
        monday_of_last_week = monday_of_last_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        logging.debug(f"Last full work week: {monday_of_last_week.strftime('%Y-%m-%d')} to {last_friday.strftime('%Y-%m-%d')}")
        
        return {
            'start_date': monday_of_last_week,
            'end_date': last_friday
        }
    
    @staticmethod
    def get_all_weeks_in_year(year=None):
        """Gets all weeks in the specified year from January 1st to current date"""
        weeks = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        current_year = year if year is not None else today.year
        
        # Start from first day of the year
        current_date = datetime(current_year, 1, 1)
        
        # Find the first Friday
        days_until_friday = (4 - current_date.weekday()) % 7
        current_date += timedelta(days=days_until_friday)
        
        # End date is either end of year (past years) or today
        if current_year < today.year:
            # Find the last Friday of December
            last_day = datetime(current_year, 12, 31)
            days_to_friday = (last_day.weekday() - 4) % 7  # 4 = Friday
            end_date = last_day - timedelta(days=days_to_friday)
        else:
            # Use today for current year
            end_date = today
        
        # Generate weeks until we reach the end date
        while current_date <= end_date:
            week_end = current_date
            week_start = week_end - timedelta(days=4)
            
            weeks.append({
                'start_date': week_start,
                'end_date': week_end
            })
            
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

    @staticmethod
    def get_current_week_dates():
        """Gets the date range for the current work week (Monday through Friday)"""
        today = datetime.now()
        
        # Find Monday of current week
        day_of_week = today.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday
        days_since_monday = day_of_week
        monday_of_current_week = today - timedelta(days=days_since_monday)
        monday_of_current_week = monday_of_current_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # End date is either today or upcoming Friday if today is before Friday
        if day_of_week < 4:  # Before Friday
            days_to_friday = 4 - day_of_week
            end_date = today + timedelta(days=days_to_friday)
        else:  # Friday or weekend
            end_date = today
            
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        logging.debug(f"Current work week: {monday_of_current_week.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        return {
            'start_date': monday_of_current_week,
            'end_date': end_date
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
    
    def __init__(self, api_token, api_url, workspace_id, reports_api_url=None):
        super().__init__(api_url, api_token)
        self.workspace_id = workspace_id
        self.reports_api_url = reports_api_url or api_url
        
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
        """Fetch time records from Toggl Reports API"""

        if start_date >= end_date:
            logging.debug("Start date is after end date")
            return []

        # Format dates for API request
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # Use reports API
        endpoint = f"/workspace/{self.workspace_id}/search/time_entries"
        
        try:
            payload = {
                "start_date": start_date_str,
                "end_date": end_date_str
            }
            
            url = f"{self.reports_api_url}{endpoint}"
            headers = self.get_toggl_headers()
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            time_records = response.json()
            
            return time_records
        except Exception as e:
            raise Exception(f"Failed to fetch time records: {e}")
    
    def fetch_projects(self):
        """Fetch projects from Toggl API"""
        if not self.workspace_id:
            logging.error("Cannot fetch projects: Workspace ID is missing")
            return {}
        
        endpoint = f"/workspaces/{self.workspace_id}/projects"
        
        try:
            projects = self.get(endpoint, self.get_toggl_headers())
            project_map = {project['id']: project['name'] for project in projects}
            logging.debug(f"Retrieved {len(projects)} projects from Toggl")
            return project_map
        except Exception as e:
            logging.error(f"Error fetching projects: {str(e)}")
            raise

# ============================================================================
# CONFLUENCE SERVICE
# ============================================================================

class ConfluenceService(ApiService):
    """Service for interacting with the Confluence API"""
    
    MONTH_NAMES = ["January", "February", "March", "April", "May", "June", 
                   "July", "August", "September", "October", "November", "December"]
    
    def __init__(self, base_url, api_token, space_key, page_id, username, display_name=None):
        super().__init__(base_url, api_token)
        self.space_key = space_key
        self.page_id = page_id
        self.username = username
        self.display_name = display_name or username or 'Andres'
        self.date_format = None  # Will store the detected date format
        # Precompile regex patterns for better performance
        self._month_pattern = re.compile(r'<h1>([A-Za-z]+)</h1>([\s\S]*?)(?=<h1>|$)')
        self._unpadded_date_pattern = re.compile(r'<h2>w/e (\d{1}/\d{1,2}|\d{1,2}/\d{1})</h2>')
    
    def get_existing_content(self):
        """Retrieves the existing page content for analysis"""
        page_data = self.get_page_content()
        # Choose date format for week titles
        if not self.date_format:
            self._detect_date_format(page_data['content'])
        return page_data['content']
    
    def _detect_date_format(self, content):
        """Detect if page uses zero-padded dates or not"""
        # Use the precompiled pattern
        if self._unpadded_date_pattern.search(content):
            self.date_format = "unpadded"
            logging.debug("Detected unpadded date format (e.g. w/e 1/5)")
        else:
            # Default to padded format
            self.date_format = "padded"
            logging.debug("Using padded date format (e.g. w/e 01/05)")
    
    def _check_content_exists(self, content, week_end_date):
        """Check if week and user exist in content
        Returns a tuple of (week_exists, user_exists)"""
        # Look for the week heading - try both formats if needed
        day, month = week_end_date.split('/')
        day_num = int(day)
        month_num = int(month)
        
        # Generate both formats for comparison
        padded_date = f"{day_num:02d}/{month_num:02d}"
        unpadded_date = f"{day_num}/{month_num}"
        
        # Try the specific format we've detected first
        search_date = padded_date if self.date_format == "padded" else unpadded_date
        
        week_pattern = re.compile(f'<h2>w/e {search_date}</h2>(.*?)(?=<h2>|$)', re.DOTALL)
        week_match = week_pattern.search(content)
        
        # If not found, try the other format
        if not week_match:
            alt_date = unpadded_date if self.date_format == "padded" else padded_date
            alt_pattern = re.compile(f'<h2>w/e {alt_date}</h2>(.*?)(?=<h2>|$)', re.DOTALL)
            week_match = alt_pattern.search(content)
        
        if not week_match:
            return False, False
        
        # Get the content of this week section
        week_section = week_match.group(0)
        
        # Check if user heading exists in the week section
        user_pattern = re.compile(f'<h3>{self.display_name}</h3>', re.DOTALL)
        user_exists = bool(user_pattern.search(week_section))
        
        return True, user_exists
    
    def has_week_for_user(self, content, week_end_date):
        """Checks if a specific week already has content for the current user"""
        _, user_exists = self._check_content_exists(content, week_end_date)
        return user_exists
    
    def post_report(self, formatted_content, date_range=None, replace=False):
        """Post a report to Confluence"""
        # Get current page content
        current_page_data = self.get_page_content()
        
        # Use provided date range or current dates
        week_info = self.get_week_info_from_date(date_range['end_date'] if date_range else None)
        
        # Prepare updated content
        updated_content, status = self.prepare_updated_content(
            current_page_data['content'],
            formatted_content,
            week_info,
            replace
        )
        
        # Only update if content has changed
        if updated_content != current_page_data['content']:
            self.save_page(current_page_data['title'], updated_content, current_page_data['version'])
        
        logging.info(status)
    
    def get_page_content(self):
        """Get the content of a Confluence page"""
        endpoint = f"/rest/api/content/{self.page_id}?expand=body.storage,version"
        
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
            
            logging.debug(f"Updating page with new version: {current_version + 1}")
            
            # Use requests directly for better error handling
            url = f"{self.base_url}{endpoint}"
            headers = {'Authorization': f"Bearer {self.api_token}", 'Content-Type': 'application/json'}
            
            response = requests.put(url, json=payload, headers=headers)
            
            # Detailed error handling
            if response.status_code != 200:
                error_msg = f"Error updating Confluence page: {response.status_code} response"
                try:
                    error_details = response.json()
                    if 'message' in error_details:
                        error_msg += f"\nDetails: {error_details['message']}"
                except:
                    error_msg += f"\nResponse text: {response.text[:500]}"
                
                logging.error(error_msg)
                raise Exception(error_msg)
                
            logging.debug("Confluence page updated successfully")
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error updating Confluence page: {str(e)}"
            logging.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Error updating Confluence page: {str(e)}"
            logging.error(error_msg)
            raise
    
    def prepare_updated_content(self, current_content, formatted_content, week_info, replace=False):
        """Prepare the updated content for the Confluence page"""
        month = week_info['month']
        week_end_date = week_info['week_end_date']
        
        # Check if user already has content for this week and get week existence info
        week_exists, user_exists = self._check_content_exists(current_content, week_end_date)
        
        # If user content exists and we're not replacing, return early
        if user_exists and not replace:
            return current_content, f"Report already exists for week ending {week_end_date}."
        
        # Extract all month sections and update
        month_sections = self.extract_month_sections(current_content)
        updated_sections = self.add_content_to_sections(
            month_sections, month, week_end_date, formatted_content, replace
        )
        
        # Generate ordered content
        ordered_content = self.regenerate_ordered_content(updated_sections)
        
        # Determine status message based on what we already know
        status = self._determine_status_message(month, week_end_date, user_exists, week_exists, 
                                               month in month_sections, replace)
        
        return ordered_content, status
    
    def _determine_status_message(self, month, week_end_date, user_exists, week_exists, month_exists, replace):
        """Determine appropriate status message based on what was updated"""
        if user_exists and replace:
            return f"Replaced existing report for week ending {week_end_date}."
        elif user_exists:
            return f"Report already exists for week ending {week_end_date}."
        elif week_exists:
            return f"Added report to existing week ending {week_end_date}."
        elif month_exists:
            return f"Added new week ending {week_end_date}."
        else:
            return f"Added new month '{month}'."
    
    def extract_month_sections(self, content):
        """Extracts all month sections from the content"""
        month_sections = {}
        
        for match in self._month_pattern.finditer(content):
            month_name = match.group(1)
            if month_name in self.MONTH_NAMES:
                month_sections[month_name] = match.group(0)
                logging.debug(f"Found existing month section: {month_name}")
        
        return month_sections
    
    def add_content_to_sections(self, sections, month, week_end_date, formatted_content, replace=False):
        """Add new content to the appropriate section"""
        updated_sections = sections.copy()
        
        if month in updated_sections:
            month_content = updated_sections[month]
            week_exists, user_exists = self._check_content_exists(month_content, week_end_date)
            
            if user_exists and replace:
                updated_sections[month] = self._replace_user_content(
                    month_content, week_end_date, formatted_content
                )
            elif user_exists:
                return updated_sections
            elif week_exists:
                updated_sections[month] = self._add_to_existing_week(
                    month_content, week_end_date, formatted_content
                )
            else:
                updated_sections[month] = self._add_new_week(
                    month_content, week_end_date, formatted_content
                )
        else:
            # Create new month section
            new_section = f"""
<h1>{month}</h1>
<h2>w/e {week_end_date}</h2>
<h3>{self.display_name}</h3>
{formatted_content}
"""
            updated_sections[month] = new_section
        
        return updated_sections
    
    def _replace_user_content(self, content, week_end_date, formatted_content):
        """Replace existing content for a user in a specific week"""
        # Find the week section
        week_pattern = re.compile(f'<h2>w/e {week_end_date}</h2>(.*?)(?=<h2>|$)', re.DOTALL)
        week_match = week_pattern.search(content)
        
        if not week_match:
            return content
        
        # Get the week content
        week_content = week_match.group(0)
        
        # Find the user section in this week
        user_pattern = re.compile(f'<h3>{self.display_name}</h3>(.*?)(?=<h3>|<h2>|$)', re.DOTALL)
        user_match = user_pattern.search(week_content)
        
        if not user_match:
            return content
        
        # Replace the user's content
        user_section_start = user_match.start() + len(f'<h3>{self.display_name}</h3>')
        user_section_end = user_match.end()
        
        replaced_week_content = (
            week_content[:user_section_start] + 
            "\n" + formatted_content + 
            week_content[user_section_end:]
        )
        
        # Replace the entire week section in the content
        return content.replace(week_content, replaced_week_content)
    
    def _add_to_existing_week(self, content, week_end_date, formatted_content):
        """Add user section to existing week"""
        # Find the week section
        week_pattern = re.compile(f'<h2>w/e {week_end_date}</h2>(.*?)(?=<h2>|$)', re.DOTALL)
        match = week_pattern.search(content)
        
        if not match:
            return content
        
        # Build user section
        user_section = f"<h3>{self.display_name}</h3>\n{formatted_content}"
        
        # Insert after week heading
        week_start = match.start() + len(f'<h2>w/e {week_end_date}</h2>')
        return content[:week_start] + "\n" + user_section + content[week_start:]
    
    def _add_new_week(self, content, week_end_date, formatted_content):
        """Add new week to existing month content"""
        # Parse date to compare chronologically
        day, month_num = map(int, week_end_date.split('/'))
        new_week_date = datetime.now().replace(day=day, month=month_num)
        
        # Extract all existing week headings with their positions
        week_pattern = re.compile(r'<h2>w\/e (\d{2})\/(\d{2})<\/h2>')
        weeks = []
        
        for match in week_pattern.finditer(content):
            try:
                w_day, w_month = map(int, [match.group(1), match.group(2)])
                week_date = datetime.now().replace(day=w_day, month=w_month)
                weeks.append({'date': week_date, 'pos': match.start()})
            except Exception:
                continue
        
        # Find insert position (reverse chronological order - newest first)
        insert_pos = content.find('</h1>') + 5  # Default: after the month heading
        
        for week in sorted(weeks, key=lambda w: w['date'], reverse=True):
            if week['date'] < new_week_date:
                insert_pos = week['pos']
                break
        
        # Create week section
        week_section = f"""
<h2>w/e {week_end_date}</h2>
<h3>{self.display_name}</h3>
{formatted_content}
"""
        
        return content[:insert_pos] + week_section + content[insert_pos:]
    
    def regenerate_ordered_content(self, sections):
        """Regenerate content with months in reverse chronological order"""
        # Sort months (newest first)
        months = sorted(sections.keys(), 
                       key=lambda m: self.MONTH_NAMES.index(m) if m in self.MONTH_NAMES else -1, 
                       reverse=True)
        
        return "".join(sections[month] for month in months)
    
    def get_week_info_from_date(self, date=None):
        """Get month name and week ending date from a date, using the detected format"""
        date = date or DateUtils.get_last_friday()
        
        # Format date according to detected pattern (or default to padded)
        if self.date_format == "unpadded":
            week_end_date = date.strftime('%-d/%-m')  # No leading zeros
        else:
            week_end_date = date.strftime('%d/%m')    # With leading zeros
        
        return {
            'month': date.strftime('%B'),
            'week_end_date': week_end_date
        }

# ============================================================================
# FORMATTING UTILITIES
# ============================================================================

def format_time_records(time_records, project_map):
    """Format time records into HTML for Confluence"""
    if not time_records:
        return "No time records found for the last week."
    
    # Group time entries by project and task
    project_groups = {}
    for record in time_records:
        project_id = record.get('project_id')
        project_name = project_map.get(project_id, 'Other') if project_id else 'Other'
        
        if project_name not in project_groups:
            project_groups[project_name] = set()
        
        description = record.get('description', '').strip()
        if description:
            # Escape HTML special characters to prevent parsing errors
            escaped_description = html.escape(description)
            project_groups[project_name].add(escaped_description)
    
    # Format as HTML list
    html_output = ['<ul>']
    for project_name in sorted(project_groups.keys()):
        escaped_project = html.escape(project_name)
        html_output.append(f"<li>{escaped_project}")
        
        tasks = sorted(project_groups[project_name])
        if tasks:
            html_output.append('<ul>')
            for task in tasks:
                html_output.append(f"<li>{task}</li>")
            html_output.append('</ul>')
        
        html_output.append('</li>')
    html_output.append('</ul>')
    
    return "\n".join(html_output)

# ============================================================================
# MAIN APPLICATION LOGIC
# ============================================================================

def validate_env_vars(config):
    """Validate required environment variables"""
    required_vars = [
        {'value': config['toggl']['api_token'], 'name': 'TOGGL_API_TOKEN'},
        {'value': config['toggl']['workspace_id'], 'name': 'TOGGL_WORKSPACE_ID'},
        {'value': config['confluence']['username'], 'name': 'CONFLUENCE_USERNAME'},
        {'value': config['confluence']['api_token'], 'name': 'CONFLUENCE_API_TOKEN'},
        {'value': config['confluence']['base_url'], 'name': 'CONFLUENCE_BASE_URL'}
    ]
    
    missing_vars = [var['name'] for var in required_vars if not var['value']]
    
    if missing_vars:
        for var_name in missing_vars:
            logging.error(f"ERROR: {var_name} is not set in environment variables")
        sys.exit(1)

def process_week(toggl_service, confluence_service, date_range, existing_project_map=None, replace=False):
    """Process a single week and post to Confluence"""
    week_date_str = date_range['end_date'].strftime('%d/%m')
    logging.debug(f"Fetching time records for week ending {week_date_str}...")
    
    # Get project map once if not provided
    project_map = existing_project_map or toggl_service.fetch_projects()
    
    time_records = toggl_service.fetch_time_records(date_range['start_date'], date_range['end_date'])
    logging.info(f"Retrieved {len(time_records)} time entries")
    
    if not time_records:
        raise Exception("No time records found for this period")
    
    formatted_report = format_time_records(time_records, project_map)
    confluence_service.post_report(formatted_report, date_range, replace)

def fill_in_missing_weeks(toggl_service, confluence_service, year=None, replace=False):
    """Fill in reports for all weeks in the specified year in a single update"""
    all_weeks = DateUtils.get_all_weeks_in_year(year)
    year_str = year or datetime.now().year
    logging.info(f"Found {len(all_weeks)} weeks in {year_str} to process.")
    
    # Check which weeks already have reports
    existing_content = confluence_service.get_existing_content()
    
    # Fetch project map once
    project_map = toggl_service.fetch_projects()
    
    stats = {'processed': 0, 'skipped': 0, 'errors': 0, 'no_data': 0, 'replaced': 0}
    weeks_to_process = []

    # Process newest weeks first
    reversed_weeks = list(reversed(all_weeks))
    
    # First pass: collect all weeks that need processing
    for i, week in enumerate(reversed_weeks):
        # Use Confluence's format detection for week end date
        week_info = confluence_service.get_week_info_from_date(week['end_date'])
        week_end_date_str = week_info['week_end_date']
        
        week_index = len(all_weeks) - i
        logging.info(f"[{week_index}/{len(all_weeks)}] Week ending {week_end_date_str}")
        
        # Check if the week already exists
        week_exists = confluence_service.has_week_for_user(existing_content, week_end_date_str)
        if week_exists and not replace:
            logging.info(f"✓ Report already exists for week ending {week_end_date_str}. Skipping.")
            stats['skipped'] += 1
            continue
        elif week_exists and replace:
            logging.info(f"⟳ Report exists for week ending {week_end_date_str}. Will replace.")
            stats['replaced'] += 1
        
        try:
            # Fetch time records and format the report
            time_records = toggl_service.fetch_time_records(week['start_date'], week['end_date'])
            if not time_records:
                logging.info(f"ℹ No time entries found for this week. Skipping.")
                stats['no_data'] += 1
                continue
            else:
                formatted_report = format_time_records(time_records, project_map)
                if not week_exists:
                    stats['processed'] += 1
            
            # Store this week for batch processing
            weeks_to_process.append({
                'month': week_info['month'],
                'week_end_date': week_end_date_str,
                'content': formatted_report
            })
            
        except Exception as e:
            logging.error(f"✗ Error processing week: {str(e)}")
            stats['errors'] += 1
    
    # If we have weeks to process, update the page in a single batch
    if weeks_to_process:
        try:
            # Get current page content
            current_page_data = confluence_service.get_page_content()
            current_content = current_page_data['content']
            
            # Extract all month sections from current content
            month_sections = confluence_service.extract_month_sections(current_content)
            
            # Add all collected weeks to the appropriate sections
            for week in weeks_to_process:
                month_sections = confluence_service.add_content_to_sections(
                    month_sections, 
                    week['month'],
                    week['week_end_date'],
                    week['content'],
                    replace
                )
            
            # Generate the final content with proper month ordering
            final_content = confluence_service.regenerate_ordered_content(month_sections)
            
            # Update the page with all changes at once
            if final_content != current_content:
                confluence_service.save_page(
                    current_page_data['title'],
                    final_content,
                    current_page_data['version']
                )
                processed_count = stats['processed'] + stats['replaced']
                logging.info(f"Successfully updated {processed_count} weeks in a single batch.")
            else:
                logging.info("No changes needed to the page content.")
                
        except Exception as e:
            logging.error(f"✗ Error updating Confluence in batch: {str(e)}")
            stats['errors'] += 1
    else:
        logging.info("No content to update. All weeks already exist or have no data.")
    
    print_summary(stats, len(all_weeks))

def print_summary(stats, total_weeks):
    """Print a summary of the processing results"""
    logging.info("\n===== Summary =====")
    logging.info(f"Total weeks found: {total_weeks}")
    logging.info(f"Weeks successfully processed: {stats['processed']}")
    if 'replaced' in stats and stats['replaced'] > 0:
        logging.info(f"Weeks with replaced content: {stats['replaced']}")
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
    parser.add_argument('--current', action='store_true', help='Process the current week instead of the last completed week')
    parser.add_argument('--replace', action='store_true', help='Replace existing entries instead of skipping them')
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    
    if args.verbose:
        logging.debug(f"Command line args: {vars(args)}")
        logging.debug(f"Fill-in mode enabled: {args.fill_all_weeks}")
        if args.year:
            logging.debug(f"Processing year: {args.year}")
        if args.current:
            logging.debug(f"Processing current week instead of last week")
        if args.replace:
            logging.debug("Replace mode enabled: Will overwrite existing entries")
    
    # Validate environment variables
    validate_env_vars(config)
    
    # Initialize services
    toggl_service = TogglService(**config['toggl'])
    confluence_service = ConfluenceService(**config['confluence'])
    
    try:
        if args.fill_all_weeks:
            year_msg = f" for {args.year}" if args.year else ""
            logging.info(f"Fill-in mode activated. Will add reports for all missing weeks{year_msg}.")
            fill_in_missing_weeks(toggl_service, confluence_service, args.year, args.replace)
        else:
            # Use current week or last week based on the flag
            if args.current:
                logging.info("Processing the current week...")
                process_week(toggl_service, confluence_service, DateUtils.get_current_week_dates(), replace=args.replace)
            else:
                logging.info("Processing the most recent completed week...")
                process_week(toggl_service, confluence_service, DateUtils.get_last_week_dates(), replace=args.replace)
        
        logging.info("All operations completed successfully!")
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        if config['app']['debug']:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()