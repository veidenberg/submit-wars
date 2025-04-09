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
        today = datetime.now()
        current_year = year if year is not None else today.year
        
        # Start from first day of the year
        current_date = datetime(current_year, 1, 1, 0, 0, 0)
        
        # Find the first Friday
        days_until_friday = (4 - current_date.weekday()) % 7
        current_date += timedelta(days=days_until_friday)
        current_date = current_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # End date is either end of year or today
        end_date = datetime(current_year, 12, 31, 23, 59, 59) if current_year < today.year else today
        
        # Generate weeks until we reach the end date
        while current_date <= end_date:
            week_end = current_date
            week_start = week_end - timedelta(days=4)
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            
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

        # Format dates for API request
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        endpoint = f"/me/time_entries?start_date={start_date_str}&end_date={end_date_str}"
        
        try:
            time_records = self.get(endpoint, self.get_toggl_headers())
            logging.debug(f"Retrieved {len(time_records)} time entries from Toggl")
            return time_records
        except Exception as e:
            error_message = str(e)
            
            # Handle "start_date must not be earlier than" error
            if "start_date must not be earlier than" in error_message:
                date_match = re.search(r"than (\d{4}-\d{2}-\d{2})", error_message)
                if date_match:
                    earliest_date = datetime.fromisoformat(date_match.group(1))
                    self.earliest_allowed_date = earliest_date
                    logging.debug(f"Toggl API restriction: earliest allowed date is {earliest_date.isoformat()}")
                    return self.fetch_time_records(earliest_date, end_date)
            
            raise Exception(f"Failed to fetch time records: {error_message}")
    
    def _adjust_date_range(self, start_date, end_date):
        """Adjust date range based on API limitations and current time"""
        # Check if start_date is earlier than earliest allowed date
        if self.earliest_allowed_date and start_date < self.earliest_allowed_date:
            logging.debug(f"Start date {start_date.isoformat()} is earlier than the earliest allowed date {self.earliest_allowed_date.isoformat()}")
            start_date = self.earliest_allowed_date
        
        # Adjust future dates to current time
        current_time = datetime.now()
        if start_date > current_time:
            start_date = current_time
            logging.debug(f"Start date adjusted to current time: {start_date.isoformat()}")
            
        if end_date > current_time:
            end_date = current_time
            logging.debug(f"End date adjusted to current time: {end_date.isoformat()}")
            
        return start_date, end_date
    
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
    
    def get_existing_content(self):
        """Retrieves the existing page content for analysis"""
        page_data = self.get_page_content()
        return page_data['content']
    
    def _check_content_exists(self, content, week_end_date):
        """Check if week and user exist in content
        Returns a tuple of (week_exists, user_exists)"""
        # Look for the week heading
        week_pattern = re.compile(f'<h2>w/e {week_end_date}</h2>(.*?)(?=<h2>|$)', re.DOTALL)
        week_match = week_pattern.search(content)
        
        if not week_match:
            return False, False
        
        # Week exists, check if user heading exists in this week's content
        week_content = week_match.group(1)
        user_pattern = re.compile(f'<h3>{self.display_name}</h3>', re.DOTALL)
        user_exists = bool(user_pattern.search(week_content))
        
        return True, user_exists
    
    def has_week_for_user(self, content, week_end_date):
        """Checks if a specific week already has content for the current user"""
        _, user_exists = self._check_content_exists(content, week_end_date)
        return user_exists
    
    def post_report(self, formatted_content, date_range=None):
        """Post a report to Confluence"""
        # Get current page content
        current_page_data = self.get_page_content()
        
        # Use provided date range or current dates
        week_info = DateUtils.get_week_info_from_date(date_range['end_date'] if date_range else None)
        
        # Prepare updated content
        updated_content, status = self.prepare_updated_content(
            current_page_data['content'],
            formatted_content,
            week_info
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
            
            self.put(endpoint, payload, {
                'Authorization': f"Bearer {self.api_token}"
            })
            logging.debug("Confluence page updated successfully")
        except Exception as e:
            logging.error(f"Error updating Confluence page: {str(e)}")
            raise
    
    def prepare_updated_content(self, current_content, formatted_content, week_info):
        """Prepare the updated content for the Confluence page"""
        month = week_info['month']
        week_end_date = week_info['week_end_date']
        
        # Check if user already has content for this week
        _, user_exists = self._check_content_exists(current_content, week_end_date)
        
        if user_exists:
            return current_content, f"Report already exists for week ending {week_end_date}."
        
        # Extract all month sections and update
        month_sections = self.extract_month_sections(current_content)
        updated_sections = self.add_content_to_sections(
            month_sections, month, week_end_date, formatted_content
        )
        
        # Generate ordered content
        ordered_content = self.regenerate_ordered_content(updated_sections)
        
        # Determine status message
        week_exists = bool(re.search(f'<h2>w/e {week_end_date}</h2>', current_content))
        month_exists = bool(re.search(f'<h1>{month}</h1>', current_content))
        
        if user_exists:
            status = f"Report already exists for week ending {week_end_date}."
        elif week_exists:
            status = f"Added report to existing week ending {week_end_date}."
        elif month_exists:
            status = f"Added new week ending {week_end_date}."
        else:
            status = f"Added new month '{month}'."
        
        return ordered_content, status
    
    def extract_month_sections(self, content):
        """Extracts all month sections from the content"""
        month_sections = {}
        month_pattern = re.compile(r'<h1>([A-Za-z]+)</h1>([\s\S]*?)(?=<h1>|$)')
        
        for match in month_pattern.finditer(content):
            month_name = match.group(1)
            if month_name in self.MONTH_NAMES:
                month_sections[month_name] = match.group(0)
                logging.debug(f"Found existing month section: {month_name}")
        
        return month_sections
    
    def add_content_to_sections(self, sections, month, week_end_date, formatted_content):
        """Add new content to the appropriate section"""
        updated_sections = sections.copy()
        
        if month in updated_sections:
            month_content = updated_sections[month]
            week_exists, user_exists = self._check_content_exists(month_content, week_end_date)
            
            if user_exists:
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
        project_id = record.get('pid')
        project_name = project_map.get(project_id, 'No Project') if project_id else 'No Project'
        
        if project_name not in project_groups:
            project_groups[project_name] = set()
        
        description = record.get('description', '').strip()
        if description:
            project_groups[project_name].add(description)
    
    # Format as HTML list
    html = ['<ul>']
    for project_name in sorted(project_groups.keys()):
        html.append(f"<li>{project_name}")
        
        tasks = sorted(project_groups[project_name])
        if tasks:
            html.append('<ul>')
            for task in tasks:
                html.append(f"<li>{task}</li>")
            html.append('</ul>')
        
        html.append('</li>')
    html.append('</ul>')
    
    return "\n".join(html)

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

def process_week(toggl_service, confluence_service, date_range, existing_project_map=None):
    """Process a single week and post to Confluence"""
    week_date_str = date_range['end_date'].strftime('%d/%m')
    logging.debug(f"Fetching time records for week ending {week_date_str}...")
    
    # Get project map once if not provided
    project_map = existing_project_map or toggl_service.fetch_projects()
    
    time_records = toggl_service.fetch_time_records(date_range['start_date'], date_range['end_date'])
    logging.info(f"Retrieved {len(time_records)} time entries")
    
    if not time_records:
        raise Exception("No time records found for this period")
    
    # Debug info
    if time_records and logging.getLogger().level == logging.DEBUG:
        logging.debug(f"Sample time record: {json.dumps(time_records[0:1])}")
    
    formatted_report = format_time_records(time_records, project_map)
    confluence_service.post_report(formatted_report, date_range)

def fill_in_missing_weeks(toggl_service, confluence_service, year=None):
    """Fill in reports for all missing weeks in the specified year"""
    all_weeks = DateUtils.get_all_weeks_in_year(year)
    year_str = year or datetime.now().year
    logging.info(f"Found {len(all_weeks)} weeks in {year_str} to process.")
    
    # Check which weeks already have reports
    existing_content = confluence_service.get_existing_content()
    
    # Fetch project map once
    project_map = toggl_service.fetch_projects()
    
    stats = {'processed': 0, 'skipped': 0, 'errors': 0, 'no_data': 0}
    
    # Process newest weeks first to find API limits
    reversed_weeks = list(reversed(all_weeks))
    
    for i, week in enumerate(reversed_weeks):
        week_end_date_str = week['end_date'].strftime('%d/%m')
        week_index = len(all_weeks) - i
        logging.info(f"[{week_index}/{len(all_weeks)}] Week ending {week_end_date_str}")
        
        # Skip if already exists
        if confluence_service.has_week_for_user(existing_content, week_end_date_str):
            logging.info(f"✓ Already exists. Skipping.")
            stats['skipped'] += 1
            continue
        
        try:
            process_week(toggl_service, confluence_service, week, project_map)
            stats['processed'] += 1
            
            # Add delay between requests
            if i < len(reversed_weeks) - 1:
                import time
                time.sleep(2)
                
        except Exception as e:
            if "No time records found" in str(e):
                logging.info(f"ℹ No time entries found for this week. Skipping.")
                stats['no_data'] += 1
            else:
                logging.error(f"✗ Error: {str(e)}")
                stats['errors'] += 1
    
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
    
    if args.verbose:
        logging.debug(f"Command line args: {vars(args)}")
        logging.debug(f"Fill-in mode enabled: {args.fill_all_weeks}")
        if args.year:
            logging.debug(f"Processing year: {args.year}")
    
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
            year_msg = f" for {args.year}" if args.year else ""
            logging.info(f"Fill-in mode activated. Will add reports for all missing weeks{year_msg}.")
            fill_in_missing_weeks(toggl_service, confluence_service, args.year)
        else:
            # Regular mode - process most recent week
            logging.info("Processing the most recent week...")
            process_week(toggl_service, confluence_service, DateUtils.get_last_week_dates())
        
        logging.info("All operations completed successfully!")
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        if config['app']['debug']:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()