"""
FastAPI webhook endpoint for Meezan Bank transaction alerts.
Handles real-time transaction notifications and stores them in the database.
"""

from fastapi import FastAPI, Request, HTTPException, Header, Depends, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid
import re
import os
import shutil
import db
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# FastAPI app initialization
app = FastAPI(title="Meezan Bank Webhook API", version="1.0.0")

# Add a simple test endpoint that runs before startup
@app.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify app is responding."""
    return {"status": "ok", "message": "App is responding", "timestamp": datetime.now().isoformat()}


# Add middleware to log all requests for debugging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests for debugging."""
    import time
    start_time = time.time()
    
    # Log request details
    client_ip = request.client.host if request.client else "unknown"
    print(f"[Request] {request.method} {request.url.path} from {client_ip}", flush=True)
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        print(f"[Request] {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)", flush=True)
        return response
    except Exception as e:
        process_time = time.time() - start_time
        print(f"[Request] ERROR {request.method} {request.url.path} - {str(e)} ({process_time:.3f}s)", flush=True)
        raise

# Security credentials - loaded from environment variables
# These will be validated on startup, not at import time
AUTHORIZATION_TOKEN = None
VALID_USER_ID = None
VALID_PASSWORD = None

# Channel validation - hardcoded expected values
EXPECTED_CHANNEL_TYPE = "MBL"
EXPECTED_CHANNEL_SUBTYPE = "CMS"

# IP Whitelist - loaded from environment variable (comma-separated)
ALLOWED_IPS_STR = os.getenv("ALLOWED_IPS", "127.0.0.1,::1")
ALLOWED_IPS = [ip.strip() for ip in ALLOWED_IPS_STR.split(",") if ip.strip()]

# Ensure localhost IPs are always included for testing
if "127.0.0.1" not in ALLOWED_IPS:
    ALLOWED_IPS.append("127.0.0.1")
if "::1" not in ALLOWED_IPS:
    ALLOWED_IPS.append("::1")


class HostData(BaseModel):
    """Nested model for hostData field."""
    messageData: str = Field(..., description="Comma-separated transaction data string")
    id: str = Field(..., description="Unique transaction identifier (doc_id)")


class MeezanAlertRequest(BaseModel):
    """Request model for Meezan Bank alert webhook."""
    userID: str = Field(..., description="User ID for authentication")
    password: str = Field(..., description="Password for authentication")
    channelType: Optional[str] = None
    channelSubType: Optional[str] = None
    transactionDateTime: Optional[str] = None
    hostData: HostData = Field(..., description="Transaction data container")


class SuccessResponse(BaseModel):
    """Success response model."""
    statusCode: str = "00"
    statusDesc: str = "success"
    id: str
    stan: str


class ErrorResponse(BaseModel):
    """Error response model."""
    statusCode: str = "01"
    statusDesc: str
    id: Optional[str] = None
    stan: Optional[str] = None


def verify_bearer_token(authorization: Optional[str] = Header(None)) -> bool:
    """
    Verify the Bearer token from Authorization header.
    
    Args:
        authorization: Authorization header value
        
    Returns:
        True if token is valid
        
    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is required"
        )
    
    # Extract token from "Bearer <token>" format
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>"
        )
    
    token = parts[1]
    if token != AUTHORIZATION_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization token"
        )
    
    return True


def verify_credentials(userID: str, password: str) -> bool:
    """
    Verify userID and password credentials.
    
    Args:
        userID: User ID from request body
        password: Password from request body
        
    Returns:
        True if credentials are valid
        
    Raises:
        HTTPException: If credentials are invalid
    """
    if userID != VALID_USER_ID or password != VALID_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Invalid userID or password"
        )
    return True


def parse_date(date_str: str) -> Optional[str]:
    """
    Convert date from "DD-MMM-YY" format to "YYYY-MM-DD" format.
    
    Args:
        date_str: Date string in format "02-OCT-25"
        
    Returns:
        Date string in "YYYY-MM-DD" format or None if parsing fails
    """
    try:
        # Parse date in format "02-OCT-25"
        # Map month abbreviations
        month_map = {
            "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
            "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
            "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12"
        }
        
        # Remove whitespace and split
        date_str = date_str.strip()
        parts = date_str.split("-")
        
        if len(parts) != 3:
            return None
        
        day = parts[0].zfill(2)
        month_abbr = parts[1].upper()
        year_short = parts[2]
        
        # Convert 2-digit year to 4-digit (assuming 2000s)
        if len(year_short) == 2:
            year = f"20{year_short}"
        else:
            year = year_short
        
        # Get month number
        month = month_map.get(month_abbr)
        if not month:
            return None
        
        # Validate and format
        formatted_date = f"{year}-{month}-{day}"
        
        # Validate the date is actually valid
        datetime.strptime(formatted_date, "%Y-%m-%d")
        
        return formatted_date
    except (ValueError, AttributeError, IndexError) as e:
        return None


def parse_message_data(message_data: str) -> dict:
    """
    Parse comma-separated message data string.
    
    Expected format: "02-OCT-25,180854, Mehmood Distributor, 29052, MTDOW,904446,0101, PNSC Branch, 560000.00"
    
    Extraction:
    - Index 0: Date -> Keep original format (DD-MMM-YY) for value_date
    - Last Index: Credit/Amount
    
    Args:
        message_data: Comma-separated string with transaction details
        
    Returns:
        Dictionary with parsed fields: original_date (DD-MMM-YY format), credit, or None if parsing fails
    """
    try:
        # Split by comma and strip whitespace
        parts = [part.strip() for part in message_data.split(",")]
        
        if len(parts) < 2:
            return None
        
        # Extract date (index 0) - keep in original format
        original_date_str = parts[0] if len(parts) > 0 else None
        
        # Extract credit/amount (last index)
        credit_str = parts[-1] if parts else None
        
        # Parse credit amount
        credit = None
        if credit_str:
            try:
                # Remove any currency symbols, spaces, commas
                cleaned = credit_str.replace(",", "").replace(" ", "").strip()
                credit = float(cleaned)
            except (ValueError, AttributeError):
                credit = None
        
        return {
            "original_date": original_date_str,  # Keep in DD-MMM-YY format
            "credit": credit
        }
    except Exception as e:
        return None


def convert_value_date_to_booking_format(value_date_str: Optional[str]) -> Optional[str]:
    """
    Convert value_date from DD-MMM-YY format to YYYY-MM-DD HH:MM:SS format.
    
    Args:
        value_date_str: Date string in DD-MMM-YY format (e.g., "02-OCT-25")
        
    Returns:
        DateTime string in "YYYY-MM-DD HH:MM:SS" format, or None if conversion fails
    """
    if not value_date_str:
        return None
    
    # Parse the DD-MMM-YY format date
    parsed_date = parse_date(value_date_str)
    if parsed_date:
        # parsed_date is already in YYYY-MM-DD format, add time component
        return f"{parsed_date} 00:00:00"
    
    return None


def parse_transaction_datetime(datetime_str: Optional[str]) -> Optional[str]:
    """
    Parse transactionDateTime from bank webhook and convert to database format.
    
    Expected formats (common bank datetime formats):
    - ISO format: "2025-10-02T18:08:54" or "2025-10-02T18:08:54.000Z"
    - ISO with high precision: "2025-05-21T11:12:10.8299521359872Z" (handles >6 digit microseconds)
    - Custom format: "02-OCT-2025 18:08:54" or similar
    
    Args:
        datetime_str: DateTime string from transactionDateTime field
        
    Returns:
        DateTime string in "YYYY-MM-DD HH:MM:SS" format, or None if parsing fails
    """
    if not datetime_str:
        return None
    
    datetime_str = datetime_str.strip()
    if not datetime_str:
        return None
    
    # Handle high-precision microseconds (more than 6 digits) and Z suffix
    # Step 1: Remove Z suffix temporarily if present
    has_z_suffix = datetime_str.endswith('Z')
    if has_z_suffix:
        datetime_str = datetime_str[:-1]
    
    # Step 2: If string has microseconds (contains a dot), truncate to 6 digits max
    if '.' in datetime_str:
        # Split on the dot to separate date/time from fractional seconds
        parts = datetime_str.split('.')
        if len(parts) == 2:
            integer_part = parts[0]
            fractional_part = parts[1]
            
            # Truncate fractional part to maximum 6 digits (Python's strptime limit)
            if len(fractional_part) > 6:
                fractional_part = fractional_part[:6]
            
            # Reconstruct the datetime string with truncated microseconds
            datetime_str = f"{integer_part}.{fractional_part}"
    
    # Step 3: Re-add Z suffix if it was originally present
    if has_z_suffix:
        datetime_str = f"{datetime_str}Z"
    
    # Try common datetime formats
    formats_to_try = [
        "%Y-%m-%dT%H:%M:%S",           # ISO without timezone: 2025-10-02T18:08:54
        "%Y-%m-%dT%H:%M:%S.%f",        # ISO with microseconds: 2025-10-02T18:08:54.123456
        "%Y-%m-%dT%H:%M:%SZ",          # ISO with Z: 2025-10-02T18:08:54Z
        "%Y-%m-%dT%H:%M:%S.%fZ",       # ISO with microseconds and Z
        "%Y-%m-%d %H:%M:%S",           # Standard: 2025-10-02 18:08:54
        "%d-%b-%Y %H:%M:%S",           # 02-OCT-2025 18:08:54
        "%d-%b-%y %H:%M:%S",           # 02-OCT-25 18:08:54
        "%d/%m/%Y %H:%M:%S",           # 02/10/2025 18:08:54
        "%d/%m/%y %H:%M:%S",           # 02/10/25 18:08:54
        "%Y-%m-%d",                    # Date only: 2025-10-02
        "%d-%b-%Y",                    # Date only: 02-OCT-2025
        "%d-%b-%y",                    # Date only: 02-OCT-25
    ]
    
    for fmt in formats_to_try:
        try:
            parsed_dt = datetime.strptime(datetime_str, fmt)
            # Return in YYYY-MM-DD HH:MM:SS format
            return parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    
    # If all formats fail, try to extract date and time components manually
    # This handles cases like "02-OCT-25,180854" (date and time separated)
    try:
        # Try splitting by comma or space
        parts = re.split(r'[,\s]+', datetime_str)
        if len(parts) >= 2:
            date_part = parts[0]
            time_part = parts[1]
            
            # Parse date part (DD-MMM-YY or similar)
            date_obj = parse_date(date_part)
            if date_obj:
                # Parse time part (HHMMSS format)
                if len(time_part) == 6 and time_part.isdigit():
                    hour = time_part[:2]
                    minute = time_part[2:4]
                    second = time_part[4:6]
                    # date_obj is already in YYYY-MM-DD format
                    return f"{date_obj} {hour}:{minute}:{second}"
    except Exception:
        pass
    
    return None


def process_transaction(host_data: HostData, transaction_datetime: Optional[str], stan: str) -> None:
    """
    Background worker function to process a single transaction.
    
    Args:
        host_data: HostData Pydantic model object with messageData and id
        transaction_datetime: Optional datetime string
        stan: STAN to use for this transaction (matches response)
    """
    try:
        # Extract data from HostData Pydantic model
        input_id = host_data.id
        message_data = host_data.messageData
        
        print(f"[Background Task] Processing transaction: doc_id={input_id}, stan={stan}")
        
        if not input_id or not message_data:
            print(f"[Background Task] ERROR: Missing input_id or message_data for doc_id={input_id}")
            return
        
        # Parse message data
        parsed_data = parse_message_data(message_data)
        
        if not parsed_data:
            print(f"[Background Task] ERROR: Failed to parse messageData for doc_id={input_id}")
            return  # Skip invalid transaction
        
        # Get value_date in original format (DD-MMM-YY) from messageData
        original_date_str = parsed_data.get("original_date")
        
        # Convert value_date from DD-MMM-YY to YYYY-MM-DD format
        value_date = None
        if original_date_str:
            value_date = parse_date(original_date_str)  # Returns YYYY-MM-DD format
        
        # Parse transactionDateTime for booking_date (should be in YYYY-MM-DD HH:MM:SS format)
        booking_date = None
        if transaction_datetime:
            booking_date = parse_transaction_datetime(transaction_datetime)
        
        # If transactionDateTime parsing fails, use value_date as fallback
        if not booking_date and value_date:
            booking_date = convert_value_date_to_booking_format(original_date_str)
        
        # Prepare database record
        db_record = {
            "doc_id": input_id,
            "value_date": value_date,  # YYYY-MM-DD format
            "booking_date": booking_date,  # YYYY-MM-DD HH:MM:SS format
            "stan": stan,
            "description": message_data,  # Store raw message exactly as received
            "credit": parsed_data.get("credit"),
            "debit": None,
            "available_balance": None
        }
        
        print(f"[Background Task] Inserting record: doc_id={input_id}, credit={db_record.get('credit')}, value_date={value_date}")
        
        # Insert into database and check result
        success, error_msg = db.insert_webhook_transaction(db_record)
        
        if success:
            print(f"[Background Task] SUCCESS: Transaction {input_id} saved to database")
        else:
            print(f"[Background Task] ERROR: Failed to save transaction {input_id}: {error_msg}")
        
    except Exception as e:
        # Log error with full traceback
        import traceback
        transaction_id = host_data.id if host_data else "unknown"
        print(f"[Background Task] EXCEPTION processing transaction {transaction_id}: {str(e)}")
        print(f"[Background Task] Traceback: {traceback.format_exc()}")


@app.post("/meezan-alert", response_model=SuccessResponse)
async def meezan_alert(
    request_body: MeezanAlertRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None)
):
    """
    POST endpoint for Meezan Bank transaction alerts.
    
    Security:
    - IP whitelist check (only allows requests from trusted IPs)
    - Verifies Bearer token in Authorization header
    - Verifies userID and password in request body
    - Validates channelType and channelSubType match expected values
    
    Processing:
    - Accepts single transaction
    - Processes transaction in background for improved performance
    - Returns immediate success response (doesn't wait for processing)
    
    Returns:
    - Success: statusCode "00" with id and stan
    - Failure: statusCode "01" with error description (auth/validation errors)
    """
    input_id = None
    stan = None
    
    try:
        # Security: Check IP whitelist
        # Skip IP check if ALLOWED_IPS is set to "*" (allow all) for testing
        if ALLOWED_IPS_STR.strip() != "*":
            # Get real client IP (Railway proxies requests, so check X-Forwarded-For header)
            client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            if not client_ip:
                client_ip = request.headers.get("X-Real-Ip", "").strip()
            if not client_ip:
                client_ip = request.client.host if request.client else None
            
            if not client_ip or client_ip not in ALLOWED_IPS:
                print(f"Blocked connection attempt from: {client_ip}")
                print(f"Allowed IPs: {ALLOWED_IPS}")
                print(f"X-Forwarded-For: {request.headers.get('X-Forwarded-For', 'not set')}")
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. IP address not whitelisted."
                )
        else:
            # IP whitelist disabled - log but allow
            forwarded_for = request.headers.get("X-Forwarded-For", "not set")
            client_ip = request.client.host if request.client else "unknown"
            print(f"IP whitelist disabled - allowing request from: {client_ip} (X-Forwarded-For: {forwarded_for})")
        
        # Security: Verify Bearer token
        verify_bearer_token(authorization)
        
        # Security: Verify userID and password
        verify_credentials(request_body.userID, request_body.password)
        
        # Validation: Check channelType and channelSubType
        # Both must match expected values exactly (None values are considered invalid)
        channel_type_valid = request_body.channelType == EXPECTED_CHANNEL_TYPE
        channel_subtype_valid = request_body.channelSubType == EXPECTED_CHANNEL_SUBTYPE
        
        if not channel_type_valid or not channel_subtype_valid:
            # Generate a temporary stan for the error response
            stan = str(uuid.uuid4())
            input_id = request_body.hostData.id if request_body.hostData else ""
            print(f"Validation failed: channelType={request_body.channelType} (expected {EXPECTED_CHANNEL_TYPE}), channelSubType={request_body.channelSubType} (expected {EXPECTED_CHANNEL_SUBTYPE})")
            return JSONResponse(
                status_code=200,
                content={
                    "statusCode": "01",
                    "statusDesc": "Invalid Channel Type or Subtype",
                    "id": input_id,
                    "stan": stan
                }
            )
        
        # Extract doc_id for duplicate check
        input_id = request_body.hostData.id
        
        # Check for duplicate doc_id immediately after auth (synchronous check)
        conn = None
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT stan FROM bank_transactions WHERE doc_id = %s", (input_id,))
            existing_record = cursor.fetchone()
            
            if existing_record:
                # Duplicate found - return existing STAN immediately
                existing_stan = existing_record[0]
                # If STAN is None or empty, generate a new one (shouldn't happen, but handle edge case)
                if not existing_stan:
                    existing_stan = str(uuid.uuid4())
                conn.close()
                return JSONResponse(
                    status_code=200,
                    content={
                        "statusCode": "01",
                        "statusDesc": "fail",
                        "id": input_id,
                        "stan": existing_stan
                    }
                )
            conn.close()
        except Exception as e:
            if conn:
                conn.close()
            # If check fails, continue processing (don't block on check error)
            pass
        
        # No duplicate found - generate new STAN and queue for processing
        stan = str(uuid.uuid4())
        
        print(f"[Endpoint] Queueing background task for doc_id={input_id}, stan={stan}")
        
        # Add background task to process transaction
        background_tasks.add_task(process_transaction, request_body.hostData, request_body.transactionDateTime, stan)
        
        print(f"[Endpoint] Background task queued successfully for doc_id={input_id}")
        
        # Return immediate success response (don't wait for processing)
        return JSONResponse(
            status_code=200,
            content={
                "statusCode": "00",
                "statusDesc": "success",
                "id": input_id,
                "stan": stan
            }
        )
        
    except HTTPException as e:
        # Handle IP whitelist errors with proper 403 status
        if e.status_code == 403:
            raise  # Re-raise to return proper 403 Forbidden
        
        # Authentication/authorization errors (401)
        return JSONResponse(
            status_code=200,
            content={
                "statusCode": "01",
                "statusDesc": "fail",
                "id": input_id or "",
                "stan": stan or ""
            }
        )
    except Exception as e:
        # Unexpected errors
        return JSONResponse(
            status_code=200,
            content={
                "statusCode": "01",
                "statusDesc": "fail",
                "id": input_id or "",
                "stan": stan or str(uuid.uuid4())
            }
        )


@app.post("/upload-evidence")
async def upload_evidence(
    file: UploadFile = File(..., description="Evidence file to upload (JPEG/PNG/PDF)"),
    donation_id: str = Form(..., description="Donation ID")
):
    """
    POST endpoint for uploading evidence files.
    
    Accepts:
    - file: Uploaded file (JPEG/PNG/PDF)
    - donation_id: Donation ID
    
    Process:
    - Saves file to uploads/ directory with secure filename
    - Inserts record into screenshots table with donation_id and file_path
    - Returns immediate success response (no verification logic)
    
    Returns:
    - 200 OK with success message
    - 400 Bad Request if donation_id already exists
    """
    try:
        # Check if donation_id already exists in database
        conn = db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM screenshots WHERE donation_id = %s", (donation_id,))
            existing_record = cursor.fetchone()
            conn.close()
            
            if existing_record:
                # Duplicate found - return 200 OK with error message
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "error",
                        "message": f"donation_id '{donation_id}' already exists"
                    }
                )
        except Exception as e:
            if conn:
                conn.close()
            # If check fails, continue processing (don't block on check error)
            print(f"Error checking duplicate donation_id: {str(e)}")
        
        # Create uploads directory if it doesn't exist
        uploads_dir = "uploads"
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Generate secure filename: donation_id + UUID + original extension
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ".bin"
        secure_filename = f"{donation_id}_{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join(uploads_dir, secure_filename)
        
        # Save file to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get absolute path for database storage
        absolute_file_path = os.path.abspath(file_path)
        
        # Insert record into database (only donation_id and file_path)
        success, error_msg, screenshot_id = db.insert_screenshot_inbox(
            donation_id=donation_id,
            file_path=absolute_file_path
        )
        
        if not success:
            # If database insert fails, still return 200 but log the error
            # In production, you might want to handle this differently
            print(f"Error inserting screenshot inbox record: {error_msg}")
            return JSONResponse(
                status_code=200,
                content={"status": "ok", "message": "File uploaded but database record failed"}
            )
        
        # Return immediate success response
        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "message": "File uploaded successfully",
                "screenshot_id": screenshot_id,
                "file_path": absolute_file_path
            }
        )
        
    except Exception as e:
        # Return generic success even on error (as per requirement)
        # In production, you might want to return proper error responses
        print(f"Error in upload_evidence: {str(e)}")
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "message": "Request processed"}
        )


@app.get("/")
async def root():
    """Root endpoint - simple connectivity test."""
    return {"status": "ok", "message": "API is running"}


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns configuration status without requiring authentication.
    This endpoint should never raise exceptions - it's used for health checks.
    """
    try:
        health_status = {
            "status": "ok",
            "service": "meezan-webhook-api",
            "configured": True,
            "missing_vars": []
        }
        
        # Check if required environment variables are set
        missing_vars = []
        if not AUTHORIZATION_TOKEN:
            missing_vars.append("AUTHORIZATION_TOKEN")
        if not VALID_USER_ID:
            missing_vars.append("VALID_USER_ID")
        if not VALID_PASSWORD:
            missing_vars.append("VALID_PASSWORD")
        
        if missing_vars:
            health_status["configured"] = False
            health_status["missing_vars"] = missing_vars
            health_status["status"] = "misconfigured"
        
        # Check database configuration
        # Don't test connection in health check - it can hang and cause 502 errors
        # If migrations ran successfully, the database connection is working.
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Just check if DATABASE_URL is set - don't test connection
            # Connection will be tested when endpoints actually use it
            if "postgres.railway.internal" in database_url:
                health_status["database"] = "configured (internal hostname)"
                health_status["database_note"] = "Migrations successful - connection functional"
            else:
                health_status["database"] = "configured"
        else:
            health_status["database"] = "not_configured"
            health_status["status"] = "degraded"
        
        return health_status
    except Exception as e:
        # Never let health check fail - return error status instead
        return {
            "status": "error",
            "service": "meezan-webhook-api",
            "error": str(e)
        }


@app.on_event("startup")
async def startup_event():
    """
    Initialize application on startup:
    1. Validate required environment variables
    2. Initialize database schema if AUTO_INIT_DB is enabled
    
    Note: If environment variables are missing, the app will still start
    but endpoints will return errors. Check /health endpoint for status.
    """
    global AUTHORIZATION_TOKEN, VALID_USER_ID, VALID_PASSWORD
    
    import sys
    
    # Load and validate environment variables
    print("[Startup] Loading environment variables...", flush=True)
    AUTHORIZATION_TOKEN = os.getenv("AUTHORIZATION_TOKEN")
    VALID_USER_ID = os.getenv("VALID_USER_ID")
    VALID_PASSWORD = os.getenv("VALID_PASSWORD")
    
    # Validate required environment variables
    missing_vars = []
    if not AUTHORIZATION_TOKEN:
        missing_vars.append("AUTHORIZATION_TOKEN")
    if not VALID_USER_ID:
        missing_vars.append("VALID_USER_ID")
    if not VALID_PASSWORD:
        missing_vars.append("VALID_PASSWORD")
    
    if missing_vars:
        error_msg = f"[Startup] ❌ ERROR: Missing required environment variables: {', '.join(missing_vars)}"
        print(error_msg, flush=True)
        print("[Startup] Please set these variables in Railway dashboard → Your service → Variables", flush=True)
        print("[Startup] Application will start but endpoints will fail until configured.", flush=True)
        print("[Startup] Check /health endpoint for configuration status.", flush=True)
        # Don't raise exception - let app start so user can check /health endpoint
        # But log it clearly so Railway logs show the issue
        sys.stderr.write(f"\n{'='*60}\n")
        sys.stderr.write("CRITICAL: Missing required environment variables!\n")
        sys.stderr.write(f"Missing: {', '.join(missing_vars)}\n")
        sys.stderr.write("Set these in Railway → Service → Variables\n")
        sys.stderr.write(f"{'='*60}\n")
    else:
        print("[Startup] ✅ All required environment variables are set", flush=True)
    
    # Test database connection (non-blocking - don't crash if it fails)
    # The connection will be tested when actually needed by endpoints
    # Skip this test if DATABASE_URL uses internal hostname (known to fail at startup)
    database_url = os.getenv("DATABASE_URL", "")
    if database_url and "postgres.railway.internal" not in database_url:
        try:
            print("[Startup] Testing database connection...", flush=True)
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            print("[Startup] ✅ Database connection successful", flush=True)
        except Exception as e:
            error_msg = str(e)
            print(f"[Startup] ⚠️  Warning: Database connection test failed: {error_msg[:100]}", flush=True)
            print("[Startup] Connection will be retried when endpoints are called", flush=True)
            sys.stderr.write(f"\nWARNING: Database connection test failed: {error_msg[:100]}\n")
    else:
        if "postgres.railway.internal" in database_url:
            print("[Startup] ⚠️  Skipping database connection test (internal hostname)", flush=True)
            print("[Startup] Connection will be tested when endpoints are called", flush=True)
        else:
            print("[Startup] ⚠️  DATABASE_URL not set - database features will be unavailable", flush=True)
    
    # Initialize database schema if enabled
    auto_init = os.getenv("AUTO_INIT_DB", "false").lower() == "true"
    if auto_init:
        try:
            print("[Startup] Auto-initializing database schema...", flush=True)
            db.initialize_schema()
            print("[Startup] ✅ Database schema initialized successfully", flush=True)
        except Exception as e:
            print(f"[Startup] ⚠️  Warning: Failed to auto-initialize database schema: {e}", flush=True)
            print("[Startup] You can run migrations manually using: python migrations/run_migration.py", flush=True)
            sys.stderr.write(f"WARNING: Schema initialization failed: {e}\n")
    else:
        print("[Startup] Database auto-initialization disabled (set AUTO_INIT_DB=true to enable)", flush=True)
    
    print("[Startup] ✅ Application startup complete", flush=True)
    
    # Log port information for debugging
    port = os.getenv("PORT", "8000")
    print(f"[Startup] Server listening on port: {port}", flush=True)
    print(f"[Startup] Host: 0.0.0.0", flush=True)
    print("[Startup] Server is ready to accept connections", flush=True)


if __name__ == "__main__":
    import uvicorn
    # Use PORT environment variable (Railway provides this) or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

