# Toggl to Confluence Automation

This project automates the process of fetching time records from a Toggl Track account and posting them to a Confluence page in a formatted manner. It is designed to streamline the creation of weekly WAR (Work Activity Report) reports.

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [License](#license)

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd toggl-to-confluence
   ```

2. Install the dependencies:
   ```
   npm install
   ```

3. Create a `.env` file based on the `.env.example` file and fill in your Toggl and Confluence credentials.

## Configuration

The configuration settings, including API keys and endpoints, are located in `src/config/config.ts`. Ensure that you have the correct API tokens for both Toggl Track and Confluence.

## Usage

### Generate Report for Most Recent Week

To update the Confluence page with a report for the most recent completed work week:
```
npm start
```
With debug messages:
```
npm run start:verbose
```
Backfill reports for all missing weeks in the current year:
```
npm run fill-all-weeks # or fill-all-weeks:verbose
```

## License

This project is licensed under the MIT License. See the LICENSE file for more details.