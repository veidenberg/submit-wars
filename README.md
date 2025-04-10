# Submit WARs

It's time to submit WARs - with a single command. This python script fetches time records from your Toggl Track account and posts these to Webteam WARs Confluence page in the correct format. It can add the most recent week or backfill the whole year.

## Setup

1. Clone and install:
   ```
   git clone https://github.com/veidenberg/submit-wars
   cd submit-wars
   pip install -r requirements.txt
   ```

2. Create a `.env` file from `.env.example` and fill in the missing values (credentials, name).

## Usage

Update the Confluence page with your WAR records for the most recent complete week:
```
python submit_wars.py
```

Backfill WARs for all missing weeks in the current year:
```
python submit_wars.py --fill-all-weeks
```
Add `--year <year>` to process a specific year. Add `--verbose` for debug output.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.