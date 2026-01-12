"""
Database module for handling all database operations.
Provides functions for connecting, querying, and managing database records.
"""

import psycopg2
import pandas as pd
import re
import os
from urllib.parse import urlparse
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List


# Database configuration
SYNC_KEY = "bank_transactions_last_sync"


def normalize_date_to_db_format(date_str: Optional[str]) -> Optional[str]:
    """
    Normalize any date/datetime string to database format.
    
    Rules:
    - If datetime (has time component): Returns "YYYY-MM-DD HH:MM:SS"
    - If date only: Returns "YYYY-MM-DD"
    - Returns None if parsing fails
    
    Supports various input formats:
    - ISO: "2025-09-30T19:34:22", "2025-09-30T19:34:22.000Z"
    - Standard: "2025-09-30 19:34:22", "2025-09-30"
    - DD-MMM-YY: "30-Sep-25", "30-Sep-25 19:34:22"
    - DD-MM-YYYY: "30-09-2025", "30-09-2025 19:34:22"
    - DD/MM/YYYY: "30/09/2025", "30/09/2025 19:34:22"
    - DD MMM YYYY: "30 Sep 2025", "30 Sep 2025 19:34:22"
    
    Args:
        date_str: Date or datetime string in any format
        
    Returns:
        Normalized date string in "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS" format, or None
    """
    if not date_str:
        return None
    
    date_str = str(date_str).strip()
    if not date_str or date_str.lower() in ['none', 'null', '']:
        return None
    
    # Month abbreviation mapping
    month_map = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
        "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
        "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
    }
    
    # Try common datetime formats first
    datetime_formats = [
        "%Y-%m-%dT%H:%M:%S",           # ISO: 2025-09-30T19:34:22
        "%Y-%m-%dT%H:%M:%S.%f",        # ISO with microseconds
        "%Y-%m-%dT%H:%M:%SZ",          # ISO with Z
        "%Y-%m-%dT%H:%M:%S.%fZ",       # ISO with microseconds and Z
        "%Y-%m-%d %H:%M:%S",           # Standard: 2025-09-30 19:34:22
        "%d-%b-%Y %H:%M:%S",           # 30-Sep-2025 19:34:22
        "%d-%b-%y %H:%M:%S",           # 30-Sep-25 19:34:22
        "%d-%m-%Y %H:%M:%S",           # 30-09-2025 19:34:22
        "%d/%m/%Y %H:%M:%S",           # 30/09/2025 19:34:22
        "%d %b %Y %H:%M:%S",           # 30 Sep 2025 19:34:22
        "%d-%b-%Y %H:%M",              # 30-Sep-2025 19:34
        "%d-%b-%y %H:%M",              # 30-Sep-25 19:34
    ]
    
    for fmt in datetime_formats:
        try:
            parsed_dt = datetime.strptime(date_str, fmt)
            return parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    
    # Try date-only formats
    date_formats = [
        "%Y-%m-%d",                    # 2025-09-30
        "%d-%b-%Y",                    # 30-Sep-2025
        "%d-%b-%y",                    # 30-Sep-25
        "%d-%m-%Y",                    # 30-09-2025
        "%d/%m/%Y",                    # 30/09/2025
        "%d %b %Y",                    # 30 Sep 2025
        "%d-%m-%y",                    # 30-09-25
        "%d/%m/%y",                    # 30/09/25
    ]
    
    for fmt in date_formats:
        try:
            parsed_dt = datetime.strptime(date_str, fmt)
            return parsed_dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # Try manual parsing for DD-MMM-YY format with time (e.g., "30-Sep-25,193422")
    try:
        parts = re.split(r'[,\s]+', date_str)
        if len(parts) >= 2:
            date_part = parts[0]
            time_part = parts[1]
            
            # Parse date part (DD-MMM-YY or similar)
            date_parts = date_part.split("-")
            if len(date_parts) == 3:
                day = date_parts[0].zfill(2)
                month_abbr = date_parts[1].upper()
                year_short = date_parts[2]
                
                if len(year_short) == 2:
                    year = f"20{year_short}"
                else:
                    year = year_short
                
                month = month_map.get(month_abbr)
                if month:
                    # Parse time part (HHMMSS or HH:MM:SS format)
                    time_cleaned = time_part.replace(":", "").replace("-", "")
                    if len(time_cleaned) == 6 and time_cleaned.isdigit():
                        hour = time_cleaned[:2]
                        minute = time_cleaned[2:4]
                        second = time_cleaned[4:6]
                        formatted_date = f"{year}-{month}-{day}"
                        # Validate date
                        datetime.strptime(formatted_date, "%Y-%m-%d")
                        return f"{formatted_date} {hour}:{minute}:{second}"
    except Exception:
        pass
    
    # If all parsing fails, return None
    return None


def get_connection():
    """
    Get a connection to the PostgreSQL database.
    Uses DATABASE_URL environment variable if available (for Railway),
    otherwise falls back to local connection parameters.
    
    Returns:
        psycopg2.connection: Database connection object
    """
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # Parse DATABASE_URL (format: postgresql://user:password@host:port/database)
        # Railway and other platforms provide this format
        parsed = urlparse(database_url)
        
        # Handle postgres:// URLs (some platforms use this instead of postgresql://)
        if parsed.scheme == "postgres":
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        return psycopg2.connect(database_url)
    else:
        # Local development fallback
        # You can set these as environment variables or modify as needed
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "alkhidmat"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "")
        )


def get_max_gsheet_row() -> Optional[int]:
    """Return the highest gsheet_row currently stored in bank_transactions."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(gsheet_row) FROM bank_transactions")
        row = cursor.fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return None
    finally:
        conn.close()


def _ensure_sync_metadata_table(conn) -> None:
    """Create sync metadata table if it does not exist (PostgreSQL-compatible)."""
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sync_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def initialize_schema() -> None:
    """
    Initialize all database tables with PostgreSQL-compatible schema.
    Creates tables if they don't exist with:
    - SERIAL for auto-increment IDs
    - CURRENT_TIMESTAMP for timestamp defaults
    - Proper PostgreSQL data types
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Create sync_metadata table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_metadata (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Create bank_transactions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_transactions (
                id SERIAL PRIMARY KEY,
                booking_date TEXT,
                value_date TEXT,
                doc_id TEXT,
                stan TEXT,
                description TEXT,
                debit NUMERIC(15, 2),
                credit NUMERIC(15, 2),
                available_balance NUMERIC(15, 2),
                gsheet_row INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        # Create index on doc_id for faster lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_bank_transactions_doc_id 
            ON bank_transactions(doc_id)
            """
        )
        
        # Create verification_results table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_results (
                id SERIAL PRIMARY KEY,
                amount NUMERIC(15, 2),
                donor_name TEXT,
                date TEXT,
                transaction_id TEXT UNIQUE,
                status TEXT,
                department TEXT,
                currency TEXT,
                payment_channel TEXT,
                checks_passed INTEGER,
                checks_failed INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                gsheet_row INTEGER,
                donation_id TEXT,
                file_path TEXT
            )
            """
        )
        
        # Create index on transaction_id for faster lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_verification_results_transaction_id 
            ON verification_results(transaction_id)
            """
        )
        
        # Create screenshots table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS screenshots (
                id SERIAL PRIMARY KEY,
                verification_id INTEGER,
                donation_id TEXT,
                file_path TEXT,
                status TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                gsheet_row INTEGER
            )
            """
        )
        
        # Create index on verification_id for faster lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_screenshots_verification_id 
            ON screenshots(verification_id)
            """
        )
        
        # Create index on donation_id for faster lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_screenshots_donation_id 
            ON screenshots(donation_id)
            """
        )
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise Exception(f"Error initializing database schema: {str(e)}")
    finally:
        conn.close()


def get_last_sync_time() -> Optional[datetime]:
    """Return last time bank transactions were synced from Google Sheets."""
    conn = get_connection()
    try:
        _ensure_sync_metadata_table(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM sync_metadata WHERE key = %s", (SYNC_KEY,))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                return datetime.fromisoformat(row[0])
            except ValueError:
                return None
        return None
    finally:
        conn.close()


def update_last_sync_time(timestamp: datetime) -> None:
    """Persist the timestamp of the last successful bank transaction sync."""
    conn = get_connection()
    try:
        _ensure_sync_metadata_table(conn)
        cursor = conn.cursor()
        iso_timestamp = timestamp.isoformat()
        cursor.execute(
            """
            INSERT INTO sync_metadata (key, value, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT(key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at
            """,
            (SYNC_KEY, iso_timestamp, iso_timestamp),
        )
        conn.commit()
    finally:
        conn.close()


def clear_bank_transactions() -> None:
    """Remove all records from bank_transactions table."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_transactions")
        conn.commit()
    finally:
        conn.close()


def bulk_insert_bank_transactions(records: List[Dict[str, Any]]) -> Tuple[int, Optional[str]]:
    """
    Insert multiple bank transaction rows in a single batch.

    Args:
        records: List of dictionaries with keys matching table columns

    Returns:
        Tuple of (inserted_rows_count, error_message)
    """
    if not records:
        return 0, None

    conn = get_connection()
    try:
        cursor = conn.cursor()
        insert_sql = """
            INSERT INTO bank_transactions
            (booking_date, value_date, doc_id, description, debit, credit, available_balance, gsheet_row)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        data = [
            (
                record.get("booking_date"),
                record.get("value_date"),
                record.get("doc_id"),
                record.get("description"),
                record.get("debit"),
                record.get("credit"),
                record.get("available_balance"),
                record.get("gsheet_row"),
            )
            for record in records
        ]
        cursor.executemany(insert_sql, data)
        conn.commit()
        return cursor.rowcount, None
    except Exception as exc:
        conn.rollback()
        return 0, f"Error inserting bank transactions: {exc}"
    finally:
        conn.close()


def insert_webhook_transaction(data: dict) -> Tuple[bool, Optional[str]]:
    """
    Insert a single webhook transaction into bank_transactions table.
    
    Deduplication: Checks if doc_id (bank's unique event ID) already exists.
    If it does, the insert is ignored.
    
    Sets gsheet_row to -1 to distinguish webhook records from Google Sheet records.
    
    Args:
        data: Dictionary with keys matching table columns:
            - booking_date (optional)
            - value_date (optional)
            - doc_id (required - used for deduplication)
            - stan (optional - System Trace Audit Number)
            - description (optional)
            - debit (optional)
            - credit (optional)
            - available_balance (optional)
    
    Returns:
        Tuple of (success boolean, error_message if any)
    """
    if not data:
        return False, "No data provided"
    
    doc_id = data.get("doc_id")
    if not doc_id:
        return False, "doc_id is required for webhook transactions"
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Check if doc_id already exists (deduplication)
        cursor.execute("SELECT id FROM bank_transactions WHERE doc_id = %s", (doc_id,))
        existing = cursor.fetchone()
        if existing:
            return False, "Document ID already exists"  # Return failure for duplicate
        
        # Insert new transaction with gsheet_row = -1
        insert_sql = """
            INSERT INTO bank_transactions
            (booking_date, value_date, doc_id, stan, description, debit, credit, available_balance, gsheet_row)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            data.get("booking_date"),
            data.get("value_date"),
            doc_id,
            data.get("stan"),  # Store STAN in database
            data.get("description"),
            data.get("debit"),
            data.get("credit"),
            data.get("available_balance"),
            -1  # Set gsheet_row to -1 for webhook records
        )
        
        cursor.execute(insert_sql, params)
        conn.commit()
        return True, None
    except Exception as exc:
        conn.rollback()
        return False, f"Error inserting webhook transaction: {exc}"
    finally:
        conn.close()


def load_bank_transactions(credit_only: bool = True) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Load bank transactions from the database.
    
    Args:
        credit_only: If True, only load transactions with credit > 0 (incoming transfers)
        
    Returns:
        Tuple of (DataFrame with transactions, error message if any)
    """
    try:
        conn = get_connection()
        try:
            if credit_only:
                query = """
                    SELECT id, booking_date, value_date, doc_id, description, 
                           debit, credit, available_balance, gsheet_row
                    FROM bank_transactions 
                    WHERE credit IS NOT NULL AND credit > 0
                    ORDER BY value_date DESC, booking_date DESC
                """
            else:
                query = """
                    SELECT id, booking_date, value_date, doc_id, description, 
                           debit, credit, available_balance, gsheet_row
                    FROM bank_transactions 
                    ORDER BY value_date DESC, booking_date DESC
                """
            
            bank_df = pd.read_sql_query(query, conn)
            return bank_df, None
        finally:
            conn.close()
    except Exception as e:
        return None, f"Error loading transactions from database: {str(e)}"


def search_bank_transactions(
    amount: Optional[float] = None,
    date: Optional[str] = None,
    description_contains: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Search bank transactions with various filters.
    
    Args:
        amount: Exact amount to match
        date: Exact date to match (format: YYYY-MM-DD or DD-MMM-YY)
        description_contains: Substring to search in description
        min_amount: Minimum amount filter
        max_amount: Maximum amount filter
        date_from: Start date for date range (format: YYYY-MM-DD)
        date_to: End date for date range (format: YYYY-MM-DD)
        
    Returns:
        Tuple of (DataFrame with matching transactions, error message if any)
    """
    try:
        conn = get_connection()
        try:
            query = "SELECT * FROM bank_transactions WHERE 1=1"
            params = []
            
            if amount is not None:
                query += " AND ABS(credit - %s) < 0.01"
                params.append(amount)
            
            if date is not None:
                query += " AND (value_date = %s OR booking_date = %s)"
                params.extend([date, date])
            
            if description_contains:
                query += " AND description LIKE %s"
                params.append(f"%{description_contains}%")
            
            if min_amount is not None:
                query += " AND credit >= %s"
                params.append(min_amount)
            
            if max_amount is not None:
                query += " AND credit <= %s"
                params.append(max_amount)
            
            if date_from:
                query += " AND (value_date >= %s OR booking_date >= %s)"
                params.extend([date_from, date_from])
            
            if date_to:
                query += " AND (value_date <= %s OR booking_date <= %s)"
                params.extend([date_to, date_to])
            
            query += " ORDER BY value_date DESC, booking_date DESC"
            
            bank_df = pd.read_sql_query(query, conn, params=tuple(params) if params else None)
            return bank_df, None
        finally:
            conn.close()
    except Exception as e:
        return None, f"Error searching transactions: {str(e)}"


def insert_verification_result(
    amount: Optional[float],
    donor_name: str,
    date: str,
    transaction_id: Optional[str],
    status: str,
    department: Optional[str],
    currency: str,
    payment_channel: str,
    checks_passed: int,
    checks_failed: int,
    gsheet_row: Optional[int] = None,
    donation_id: Optional[str] = None,
    file_path: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Insert a verification result into the verification_results table.
    
    Args:
        amount: Transaction amount
        donor_name: Name of the donor/sender
        date: Transaction date (will be normalized to YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)
        transaction_id: Transaction ID/STAN
        status: Verification status (verified, not_found, wrong_receiver, etc.)
        department: Department name
        currency: Currency code (default: PKR)
        payment_channel: Payment channel (e.g., 'Bank Transfer')
        checks_passed: Number of checks that passed
        checks_failed: Number of checks that failed
        gsheet_row: Google Sheets row number (if applicable)
        donation_id: Donation ID from screenshots table
        file_path: File path from screenshots table
        
    Returns:
        Tuple of (success boolean, error message if any, inserted verification ID)
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Normalize date to database format
    normalized_date = normalize_date_to_db_format(date)
    
    query = """
        INSERT INTO verification_results 
        (amount, donor_name, date, transaction_id, status, department, 
         currency, payment_channel, 
         checks_passed, checks_failed, timestamp, gsheet_row, donation_id, file_path)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT(transaction_id) DO UPDATE SET
            amount = EXCLUDED.amount,
            donor_name = EXCLUDED.donor_name,
            date = EXCLUDED.date,
            status = EXCLUDED.status,
            department = EXCLUDED.department,
            currency = EXCLUDED.currency,
            payment_channel = EXCLUDED.payment_channel,
            checks_passed = EXCLUDED.checks_passed,
            checks_failed = EXCLUDED.checks_failed,
            timestamp = EXCLUDED.timestamp,
            gsheet_row = EXCLUDED.gsheet_row,
            donation_id = EXCLUDED.donation_id,
            file_path = EXCLUDED.file_path
        RETURNING id
    """
    
    params = (
        amount, donor_name, normalized_date, transaction_id, status, department,
        currency, payment_channel,
        checks_passed, checks_failed, timestamp, gsheet_row, donation_id, file_path
    )
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        # Get the ID from RETURNING clause (PostgreSQL doesn't support lastrowid)
        row = cursor.fetchone()
        verification_id = row[0] if row else None
        
        conn.commit()
        return True, None, verification_id
    except Exception as e:
        conn.rollback()
        return False, f"Error saving verification result: {str(e)}", None
    finally:
        conn.close()


def get_screenshot_by_verification(verification_id: int) -> Optional[Dict[str, Any]]:
    """Return the screenshot metadata for a given verification result."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM screenshots WHERE verification_id = %s LIMIT 1",
            (verification_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
    finally:
        conn.close()


def upsert_screenshot(
    verification_id: int,
    file_path: Optional[str],
    status: str,
    gsheet_row: Optional[int] = None
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Insert or update a screenshot record linked to a verification result.
    If an existing screenshot for this verification is already verified, it is returned unchanged.
    """
    if not verification_id:
        return False, "Verification ID is required to save screenshot metadata.", None

    conn = get_connection()
    try:
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute(
            "SELECT * FROM screenshots WHERE verification_id = %s LIMIT 1",
            (verification_id,)
        )
        existing = cursor.fetchone()

        if existing:
            columns = [col[0] for col in cursor.description]
            existing_dict = dict(zip(columns, existing))
            if existing_dict.get("status") == "verified":
                return True, None, existing_dict

            cursor.execute(
                """
                UPDATE screenshots
                SET file_path = %s, status = %s, gsheet_row = %s, uploaded_at = %s
                WHERE verification_id = %s
                """,
                (file_path, status, gsheet_row, timestamp, verification_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO screenshots (verification_id, file_path, status, gsheet_row, uploaded_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (verification_id, file_path, status, gsheet_row, timestamp)
            )

        conn.commit()
        cursor.execute(
            "SELECT * FROM screenshots WHERE verification_id = %s LIMIT 1",
            (verification_id,)
        )
        row = cursor.fetchone()
        columns = [col[0] for col in cursor.description]
        record = dict(zip(columns, row)) if row else None
        return True, None, record
    except Exception as e:
        conn.rollback()
        return False, f"Error saving screenshot record: {str(e)}", None
    finally:
        conn.close()


def insert_screenshot_inbox(
    donation_id: str,
    file_path: str
) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Insert a new screenshot record into the screenshots table.
    
    Args:
        donation_id: Donation ID
        file_path: Absolute path to the uploaded file
        
    Returns:
        Tuple of (success boolean, error_message if any, inserted screenshot ID)
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Insert new screenshot record with only donation_id and file_path
        cursor.execute(
            """
            INSERT INTO screenshots 
            (donation_id, file_path)
            VALUES (%s, %s)
            RETURNING id
            """,
            (donation_id, file_path)
        )
        
        row = cursor.fetchone()
        screenshot_id = row[0] if row else None
        
        conn.commit()
        return True, None, screenshot_id
    except Exception as e:
        conn.rollback()
        return False, f"Error inserting screenshot inbox record: {str(e)}", None
    finally:
        conn.close()


def update_screenshot_status(
    screenshot_id: Optional[int] = None,
    donation_id: Optional[str] = None,
    status: str = "verified",
    verification_id: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Update the status and verification_id of a screenshot record in the screenshots table.
    
    Args:
        screenshot_id: ID of the screenshot record (preferred)
        donation_id: Donation ID (alternative identifier if screenshot_id not provided)
        status: New status to set (e.g., 'verified', 'not_verified')
        verification_id: ID from verification_results table to link the screenshot
        
    Returns:
        Tuple of (success boolean, error_message if any)
    """
    if not screenshot_id and not donation_id:
        return False, "Either screenshot_id or donation_id must be provided"
    
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Build update query based on whether verification_id is provided
        if verification_id is not None:
            if screenshot_id:
                cursor.execute(
                    "UPDATE screenshots SET status = %s, verification_id = %s WHERE id = %s",
                    (status, verification_id, screenshot_id)
                )
            else:
                cursor.execute(
                    "UPDATE screenshots SET status = %s, verification_id = %s WHERE donation_id = %s",
                    (status, verification_id, donation_id)
                )
        else:
            # Only update status if verification_id is not provided
            if screenshot_id:
                cursor.execute(
                    "UPDATE screenshots SET status = %s WHERE id = %s",
                    (status, screenshot_id)
                )
            else:
                cursor.execute(
                    "UPDATE screenshots SET status = %s WHERE donation_id = %s",
                    (status, donation_id)
                )
        
        if cursor.rowcount == 0:
            conn.close()
            return False, "No screenshot record found to update"
        
        conn.commit()
        conn.close()
        return True, None
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error updating screenshot status: {str(e)}"


def get_verification_results(
    limit: Optional[int] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Get verification results from the database.
    
    Args:
        limit: Maximum number of results to return
        status: Filter by status (verified, not_found, wrong_receiver, etc.)
        date_from: Start date filter (format: YYYY-MM-DD)
        date_to: End date filter (format: YYYY-MM-DD)
        
    Returns:
        Tuple of (DataFrame with verification results, error message if any)
    """
    try:
        conn = get_connection()
        try:
            query = "SELECT * FROM verification_results WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = %s"
                params.append(status)
            
            if date_from:
                query += " AND date >= %s"
                params.append(date_from)
            
            if date_to:
                query += " AND date <= %s"
                params.append(date_to)
            
            query += " ORDER BY timestamp DESC"
            
            if limit:
                query += f" LIMIT {limit}"
            
            results_df = pd.read_sql_query(query, conn, params=tuple(params) if params else None)
            return results_df, None
        finally:
            conn.close()
    except Exception as e:
        return None, f"Error loading verification results: {str(e)}"


def get_transaction_by_id(transaction_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a single bank transaction by its ID.
    
    Args:
        transaction_id: The ID of the transaction
        
    Returns:
        Dictionary with transaction data or None if not found
    """
    try:
        conn = get_connection()
        try:
            query = "SELECT * FROM bank_transactions WHERE id = %s"
            cursor = conn.cursor()
            cursor.execute(query, (transaction_id,))
            row = cursor.fetchone()
            
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
        finally:
            conn.close()
    except Exception as e:
        return None


def get_verification_result_by_id(result_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a single verification result by its ID.
    
    Args:
        result_id: The ID of the verification result
        
    Returns:
        Dictionary with verification result data or None if not found
    """
    try:
        conn = get_connection()
        try:
            query = "SELECT * FROM verification_results WHERE id = %s"
            cursor = conn.cursor()
            cursor.execute(query, (result_id,))
            row = cursor.fetchone()
            
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
        finally:
            conn.close()
    except Exception as e:
        return None


def get_transaction_count() -> int:
    """
    Get the total count of bank transactions.
    
    Returns:
        Total number of transactions in the database
    """
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM bank_transactions")
            count = cursor.fetchone()[0]
            return count
        finally:
            conn.close()
    except Exception as e:
        return 0


def get_verification_count(status: Optional[str] = None) -> int:
    """
    Get the count of verification results.
    
    Args:
        status: Optional status filter
        
    Returns:
        Total number of verification results (optionally filtered by status)
    """
    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            if status:
                cursor.execute("SELECT COUNT(*) FROM verification_results WHERE status = %s", (status,))
            else:
                cursor.execute("SELECT COUNT(*) FROM verification_results")
            
            count = cursor.fetchone()[0]
            return count
        finally:
            conn.close()
    except Exception as e:
        return 0

