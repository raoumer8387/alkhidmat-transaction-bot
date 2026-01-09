# Transaction Verification Bot

Automated AI-powered system to verify donation transactions made to **Al-Khidmat Welfare Society** by matching transaction slip screenshots against official bank statements synced from Google Sheets.

## Features

- **AI-Powered Extraction**: Uses Google Gemini to extract transaction details from uploaded screenshots
- **Automatic Google Sheet Sync**: Background worker syncs new transactions from Google Sheets every 2 minutes
- **Database-Driven Verification**: Matches extracted data against bank transactions stored in SQLite database
- **Screenshot Management**: Automatically saves and tracks uploaded transaction slip screenshots
- **Duplicate Prevention**: Prevents re-verification of already verified transactions

## Architecture

### Components

1. **main.py** - Streamlit web application for transaction verification (includes integrated background sync)
2. **sheet_sync.py** - Google Sheets data fetching and transformation
3. **db.py** - Database operations and queries

### Database Tables

- **bank_transactions**: Stores bank transaction records synced from Google Sheets
- **verification_results**: Stores verification outcomes for each transaction
- **screenshots**: Tracks uploaded screenshot files and their verification status
- **sync_metadata**: Tracks last sync timestamp for Google Sheets

## Setup

### Prerequisites

- Python 3.8+
- Google Service Account credentials JSON file
- Google Gemini API key
- Access to Google Sheet with bank transaction data

### Installation

1. Clone or download the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure Google Service Account:
   - Create a service account in Google Cloud Console
   - Download the credentials JSON file
   - Save it as `google_cred.json` in the project root
   - Share your Google Sheet with the service account email

4. Configure Google Sheet:
   - Ensure row 5 contains column headers
   - Data starts from row 6 onwards
   - Required columns: Booking Date, Value Date, Doc No, Description, Debit, Credit, Available Balance

5. Set environment variables (optional):
   ```bash
   export BANK_SHEET_ID="your-sheet-id"
   export BANK_SHEET_NAME="Sheet1"
   export GOOGLE_SERVICE_ACCOUNT_FILE="google_cred.json"
   export BANK_SYNC_INTERVAL_MINUTES="2"
   ```

## Usage

### Starting the Streamlit Application

Start the Streamlit app:

```bash
streamlit run main.py
```

The application will:
- **Automatically start background sync** on startup (runs every 2 minutes)
- Perform an initial Google Sheet sync immediately
- Continue syncing every 2 minutes in the background
- Only add new rows (based on `gsheet_row` comparison)
- Print sync status messages to the console

The application will open in your browser where you can:
- Upload transaction slip screenshots
- View verification results
- Manually trigger Google Sheet sync via "Force Google Sheet Sync" button
- View transaction previews and database statistics

## Verification Process

### Pre-Verification (Must Pass)
- ✓ Receiver must be "Al-Khidmat Welfare Society"
- ✓ Receiver account must end with 2664

### Required Fields (All Must Match)
- ✓ Amount (exact match, ±0.01 tolerance)
- ✓ Date (exact match)
- ✓ Sender name (at least 50% word overlap)
- ✓ Sender account (last 4 digits) OR Phone (12 digits)

### Optional Field
- • Transaction ID (STAN) - Provides additional confirmation

### Verification Outcomes

- ✅ **Verified**: All required fields match - Result saved to `verification_results` table
- ❌ **Not Found**: Transaction missing or required fields don't match - Result saved to `verification_results` table
- ⛔ **Wrong Receiver**: Not sent to Al-Khidmat or wrong account

## File Structure

```
.
├── main.py              # Streamlit web application (includes background sync)
├── sheet_sync.py        # Google Sheets integration
├── db.py                # Database operations
├── requirements.txt     # Python dependencies
├── google_cred.json     # Google Service Account credentials
├── alkhidmat.db         # SQLite database (created automatically)
└── uploads/             # Directory for uploaded screenshots
```

## Google Sheet Format

The Google Sheet must follow this structure:

- **Rows 1-4**: Can contain any header/metadata (ignored)
- **Row 5**: Column headers (Booking Date, Value Date, Doc No, Description, Debit, Credit, Available Balance)
- **Row 6+**: Transaction data

## Database Schema

### bank_transactions
- `id` (INTEGER PRIMARY KEY)
- `booking_date` (TEXT)
- `value_date` (TEXT)
- `doc_no` (TEXT)
- `description` (TEXT)
- `debit` (REAL)
- `credit` (REAL)
- `available_balance` (REAL)
- `gsheet_row` (INTEGER) - Row number in Google Sheet

### verification_results
- `id` (INTEGER PRIMARY KEY)
- `amount` (REAL)
- `donor_name` (TEXT)
- `phone` (TEXT)
- `email` (TEXT)
- `date` (TEXT)
- `transaction_id` (TEXT UNIQUE)
- `status` (TEXT) - verified, not_found, wrong_receiver, date_parse_error
- `checks_passed` (INTEGER)
- `checks_failed` (INTEGER)
- `failed_checks_list` (TEXT)
- `gsheet_row` (INTEGER)
- `timestamp` (TEXT)

### screenshots
- `id` (INTEGER PRIMARY KEY)
- `verification_id` (INTEGER) - Foreign key to verification_results.id
- `file_path` (TEXT) - Absolute path to screenshot file
- `status` (TEXT) - verified or not_verified
- `uploaded_at` (TEXT)
- `gsheet_row` (INTEGER)

## Troubleshooting

### Sync Not Working
- Verify `google_cred.json` exists and is valid
- Check that Google Sheet is shared with service account email
- Background sync runs automatically when Streamlit app is running
- Check console output for sync status messages and error messages

### Verification Failing
- Ensure bank transactions are synced (check database)
- Verify screenshot quality (clear, readable text)
- Check that transaction details match bank statement format

### Database Issues
- Database file (`alkhidmat.db`) is created automatically
- If corrupted, delete the file and restart (will recreate on first sync)

## Development

### Adding New Features
- Database operations: Add functions to `db.py`
- Google Sheets sync: Modify `sheet_sync.py`
- UI changes: Update `main.py`
- Background tasks: Modify the `start_background_sync()` function in `main.py`

### Testing
- Test verification with sample transaction screenshots
- Verify sync works with test Google Sheet
- Check database integrity after operations

## License

Prototype for testing only - Not for production deployment

