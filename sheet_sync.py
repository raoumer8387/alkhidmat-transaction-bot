"""
Utilities for syncing bank transactions from Google Sheets into the database.
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import gspread
from gspread.exceptions import WorksheetNotFound, APIError
import pandas as pd
import db

DEFAULT_SPREADSHEET_ID = "1V2WghErUsoDi1Qdf-q46AiTG_cYFDZwmNBwBN-K76iU"
DEFAULT_SHEET_NAME = "Sheet1"
DEFAULT_SERVICE_ACCOUNT_FILE = "google_cred.json"
DEFAULT_SYNC_INTERVAL_MINUTES = 2

COLUMN_MAPPING = {
    "Booking Date": "booking_date",
    "Value Date": "value_date",
    "Doc No": "doc_id",
    "Description": "description",
    "Debit": "debit",
    "Credit": "credit",
    "Available Balance": "available_balance",
    # Note: "stan" column is ignored - it's for a different system
}


def _get_env(key: str, default: str) -> str:
    return os.getenv(key, default)


def _numeric(value: Optional[str]) -> Optional[float]:
    if value in (None, "", " "):
        return None
    cleaned = (
        str(value)
        .replace("PKR", "")
        .replace(",", "")
        .replace("pkr", "")
        .strip()
    )
    try:
        return float(cleaned)
    except ValueError:
        return None


def get_service_account_path() -> str:
    """Return absolute/relative path of the service account file."""
    return _get_env("GOOGLE_SERVICE_ACCOUNT_FILE", DEFAULT_SERVICE_ACCOUNT_FILE)


def credentials_available() -> bool:
    """Check whether the service account file exists."""
    return os.path.exists(get_service_account_path())


def get_spreadsheet_id() -> str:
    """Get the current spreadsheet ID being used (env var or default)."""
    return _get_env("BANK_SHEET_ID", DEFAULT_SPREADSHEET_ID)


def get_worksheet_name() -> str:
    """Get the current worksheet name being used (env var or default)."""
    return _get_env("BANK_SHEET_NAME", DEFAULT_SHEET_NAME)


def _load_dataframe_from_sheet() -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Load data from Google Sheet where:
    - Rows 1-4 are skipped
    - Row 5 contains column headers
    - Row 6 onwards contains actual data records
    """
    spreadsheet_id = _get_env("BANK_SHEET_ID", DEFAULT_SPREADSHEET_ID)
    worksheet_name = _get_env("BANK_SHEET_NAME", DEFAULT_SHEET_NAME)
    print(f"[DEBUG] Fetching from Google Sheet - ID: {spreadsheet_id}, Worksheet: '{worksheet_name}'")
    service_account_file = get_service_account_path()

    if not os.path.exists(service_account_file):
        return None, f"Service account file not found at {service_account_file}"

    try:
        client = gspread.service_account(filename=service_account_file)
        sheet = client.open_by_key(spreadsheet_id)
        
        # Try to get the worksheet, with better error handling
        try:
            worksheet = sheet.worksheet(worksheet_name)
        except WorksheetNotFound:
            # List available worksheets for better error message
            available_worksheets = [ws.title for ws in sheet.worksheets()]
            return None, (
                f"Worksheet '{worksheet_name}' not found in Google Sheet. "
                f"Available worksheets: {', '.join(available_worksheets)}. "
                f"Please set BANK_SHEET_NAME environment variable or update DEFAULT_SHEET_NAME."
            )
        except Exception as ws_exc:
            return None, f"Error accessing worksheet '{worksheet_name}': {ws_exc}"
        
        # Get all values from the sheet
        all_values = worksheet.get_all_values()
        
        if len(all_values) < 5:
            return None, "Google Sheet has less than 5 rows. Expected headers in row 5."
        
        # Row 5 (index 4) contains headers
        header_row = all_values[4]  # 0-based index: row 5 = index 4
        
        # Clean header row - remove empty strings and strip whitespace
        header_row = [h.strip() if h else "" for h in header_row]
        
        if not header_row or all(not h for h in header_row):
            return None, "Header row (row 5) is empty or invalid in Google Sheet"
        
        # Data starts from row 6 (index 5 onwards)
        if len(all_values) < 6:
            return None, "Google Sheet has no data rows (data should start from row 6)"
        
        # Extract data rows (row 6 onwards, which is index 5 onwards)
        data_rows = all_values[5:]  # Skip rows 1-5, start from row 6
        
        if not data_rows:
            return None, "Google Sheet has no data rows after header"
        
        # Create DataFrame with proper headers
        # Ensure all data rows have the same length as headers (pad with empty strings if needed)
        max_cols = len(header_row)
        normalized_data = []
        for row in data_rows:
            # Pad row if it's shorter than header, or truncate if longer
            normalized_row = (row + [""] * max_cols)[:max_cols]
            normalized_data.append(normalized_row)
        
        df = pd.DataFrame(normalized_data, columns=header_row)
        
        # Add gsheet_row column with actual row numbers (starting from 6)
        df["gsheet_row"] = range(6, len(df) + 6)
        
        # Remove any completely empty rows (where all columns except gsheet_row are empty)
        # Check all columns except gsheet_row
        data_cols = [col for col in df.columns if col != "gsheet_row"]
        df = df.dropna(subset=data_cols, how='all')
        
        # Also remove rows where all data columns are empty strings
        df = df[~df[data_cols].apply(lambda x: x.astype(str).str.strip().eq('').all(), axis=1)]
        
        if df.empty:
            return None, "Google Sheet has no valid data rows after filtering empty rows"
        
        return df, None
    except APIError as api_exc:
        return None, f"Google Sheets API error: {api_exc}. Check your service account permissions and spreadsheet access."
    except Exception as exc:
        return None, f"Error reading Google Sheet '{worksheet_name}' from spreadsheet '{spreadsheet_id}': {exc}"


def _transform_records(df: pd.DataFrame) -> List[Dict[str, object]]:
    """
    Transform DataFrame rows into database records.
    Handles all columns from COLUMN_MAPPING and preserves gsheet_row.
    """
    records: List[Dict[str, object]] = []
    
    # Get available columns from the DataFrame (case-insensitive matching)
    df_columns_lower = {col.lower(): col for col in df.columns}
    
    for _, row in df.iterrows():
        record: Dict[str, object] = {}
        
        # Map each expected column from Google Sheet to database column
        for sheet_col, db_col in COLUMN_MAPPING.items():
            # Try exact match first, then case-insensitive match
            if sheet_col in df.columns:
                value = row.get(sheet_col)
            elif sheet_col.lower() in df_columns_lower:
                value = row.get(df_columns_lower[sheet_col.lower()])
            else:
                # Column not found in sheet, set to None
                value = None
            
            # Process numeric columns
            if db_col in {"debit", "credit", "available_balance"}:
                record[db_col] = _numeric(value)
            elif db_col in {"booking_date", "value_date"}:
                # Normalize date columns to database format (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
                if value is None:
                    record[db_col] = None
                elif isinstance(value, str) and value.strip() == "":
                    record[db_col] = None
                else:
                    # Normalize date using db function
                    normalized_date = db.normalize_date_to_db_format(str(value).strip())
                    record[db_col] = normalized_date if normalized_date else None
            else:
                # Process text columns - convert empty strings to None
                if value is None:
                    record[db_col] = None
                elif isinstance(value, str) and value.strip() == "":
                    record[db_col] = None
                else:
                    record[db_col] = str(value).strip() if value else None
        
        # Always preserve gsheet_row for tracking
        gsheet_row = row.get("gsheet_row")
        if gsheet_row is not None:
            record["gsheet_row"] = int(gsheet_row)
        else:
            # Fallback: calculate from index if gsheet_row is missing
            record["gsheet_row"] = None
        
        records.append(record)
    
    return records


def _needs_sync(force: bool = False) -> bool:
    if force:
        return True
    last_sync = db.get_last_sync_time()
    if not last_sync:
        return True
    interval_minutes = int(_get_env("BANK_SYNC_INTERVAL_MINUTES", str(DEFAULT_SYNC_INTERVAL_MINUTES)))
    elapsed = datetime.utcnow() - last_sync
    if elapsed >= timedelta(minutes=interval_minutes):
        print("TIMER RAN")
        return True
    return False


def sync_bank_transactions(force: bool = False) -> Tuple[bool, str]:
    """
    Fetch the latest Google Sheet data and store it in bank_transactions table.

    Returns:
        Tuple (did_sync, message)
    """
    if not _needs_sync(force=force):
        interval_minutes = int(_get_env("BANK_SYNC_INTERVAL_MINUTES", str(DEFAULT_SYNC_INTERVAL_MINUTES)))
        next_run = db.get_last_sync_time() + timedelta(minutes=interval_minutes)
        return False, f"Bank transactions already synced. Next sync after {next_run:%Y-%m-%d %H:%M:%S} UTC."

    # Get spreadsheet ID and worksheet name for debug output
    spreadsheet_id = _get_env("BANK_SHEET_ID", DEFAULT_SPREADSHEET_ID)
    worksheet_name = _get_env("BANK_SHEET_NAME", DEFAULT_SHEET_NAME)
    print(f"[DEBUG] sync_bank_transactions: Fetching from Google Sheet - ID: {spreadsheet_id}, Worksheet: '{worksheet_name}'")
    
    df, error = _load_dataframe_from_sheet()
    if error:
        return False, error
    if df is None or df.empty:
        return False, "Google Sheet returned no data to sync."

    records = _transform_records(df)
    max_gsheet_row = db.get_max_gsheet_row()
    if max_gsheet_row is None:
        new_records = records
    else:
        new_records = [
            record for record in records
            if record.get("gsheet_row") and record["gsheet_row"] > max_gsheet_row
        ]

    if not new_records:
        db.update_last_sync_time(datetime.utcnow())
        return False, "No new rows to sync from Google Sheet."

    inserted, insert_error = db.bulk_insert_bank_transactions(new_records)
    if insert_error:
        return False, insert_error

    db.update_last_sync_time(datetime.utcnow())
    return True, f"Synced {inserted} new transactions from Google Sheet."
