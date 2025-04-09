# Automated WARS submitter

This tool fetches time records from a Toggl Track account and posts these to Webteam WARs confluence page in the correct format. It can add the most recent week or backfill all missing weeks on the WARs page.

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [License](#license)

## Installation

1. Clone and install:
   ```
   git clone https://github.com/veidenberg/warfiller
   cd warfiller
   npm install
   ```

2. Create a `.env` file from `.env.example` and fill in your Toggl and Confluence credentials.

## Usage

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