import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import re
import os
import threading
import time
from uuid import uuid4
from datetime import datetime
from PIL import Image
import io
import db
import sheet_sync
import schedule

# Configure page
st.set_page_config(
    page_title="Transaction Verification Service",
    page_icon="🏦",
    layout="wide"
)

# Backend API Key Configuration
GEMINI_API_KEY = "AIzaSyArCtg-s7yAz4w8Fc_kGMaKFuQiAn8Zyf4"  # Replace with your actual API key

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

SCREENSHOTS_DIR = "uploads"
last_sync_time = db.get_last_sync_time()


def run_sync_job():
    """Execute a forced sync and log the outcome."""
    success, message = sheet_sync.sync_bank_transactions(force=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    status = "SUCCESS" if success else "INFO"
    print(f"[{timestamp}][{status}] {message}")


def start_background_sync():
    """Start the background sync scheduler in a separate thread."""
    if 'sync_thread_started' not in st.session_state:
        st.session_state.sync_thread_started = True
        
        def sync_worker():
            """Background worker that runs the sync scheduler."""
            run_sync_job()  # Initial sync on startup
            schedule.every(2).minutes.do(run_sync_job)
            
            while True:
                schedule.run_pending()
                time.sleep(1)
        
        # Start the background thread
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()
        st.session_state.sync_thread = sync_thread


# Start background sync automatically
start_background_sync()


def configure_gemini():
    """Configure Gemini API with backend key"""
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel('gemini-flash-latest')


def extract_transaction_data(model, image):
    """Extract transaction details from image using Gemini"""

    prompt = """
    Analyze this banking transaction slip image and extract the following information in JSON format:

    {
        "transaction_id": "transaction or reference number if available, else null",
        "amount": "numeric amount only (no currency symbols)",
        "date": "date in DD-MMM-YY format (e.g., 21-Aug-25)",
        "sender_name": "sender's full name",
        "sender_account": "last 4 digits of sender's account/IBAN",
        "sender_phone": "12-digit phone number if available, else null",
        "receiver_name": "receiver's full name",
        "receiver_account": "last 4 digits of receiver's account/IBAN"
    }

    IMPORTANT:
    - Extract exact names as shown
    - For accounts, only extract the LAST 4 digits
    - For phone numbers, extract all 12 digits (e.g., 923001234567)
    - Date must be in DD-MMM-YY format
    - Amount should be numeric only
    - If any field is not found, use null

    Return ONLY the JSON, no other text.
    """

    try:
        response = model.generate_content([prompt, image])
        json_text = response.text.strip()

        # Remove markdown code blocks if present
        if json_text.startswith('```'):
            json_text = json_text.split('```')[1]
            if json_text.startswith('json'):
                json_text = json_text[4:]

        extracted_data = json.loads(json_text.strip())
        return extracted_data, None
    except Exception as e:
        return None, f"Error extracting data: {str(e)}"


def save_uploaded_screenshot_file(uploaded_file):
    """Persist uploaded screenshot to disk and return its path."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    original_name = uploaded_file.name or "screenshot"
    extension = os.path.splitext(original_name)[1].lower()
    if not extension:
        extension = ".png"
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex}{extension}"
    file_path = os.path.join(SCREENSHOTS_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return os.path.abspath(file_path)


def store_screenshot_for_verification(uploaded_file, verification_id, status, gsheet_row):
    """
    Store screenshot metadata while avoiding duplicate verified screenshots.
    Returns (success, message) where message describes action taken.
    """
    if not verification_id:
        return False, "Missing verification ID for screenshot storage."

    existing = db.get_screenshot_by_verification(verification_id)
    if existing and existing.get("status") == "verified":
        existing_path = existing.get("file_path", "existing file")
        return True, f"Existing verified screenshot reused ({existing_path})."

    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    file_path = save_uploaded_screenshot_file(uploaded_file)
    screenshot_status = 'verified' if status == 'verified' else 'not_verified'
    success, error, record = db.upsert_screenshot(
        verification_id=verification_id,
        file_path=file_path,
        status=screenshot_status,
        gsheet_row=gsheet_row
    )

    if not success:
        return False, error
    saved_path = record.get("file_path") if record else file_path
    return True, f"Screenshot metadata updated ({saved_path})."


def validate_receiver(extracted_data):
    """Validate receiver name and account number"""
    receiver_name = extracted_data.get('receiver_name', '').lower()
    receiver_account = extracted_data.get('receiver_account', '')

    # Check receiver name
    if 'al-khidmat welfare society' not in receiver_name and 'al khidmat welfare society' not in receiver_name:
        return False, "❌ **Not Received to Al-Khidmat**\n\nReceiver is not Al-khidmat Welfare Society."

    # Check receiver account last 4 digits
    if receiver_account != '2664':
        return False, f"❌ **Not Received to Al-Khidmat**\n\nReceiver account does not end with 2664 (found: {receiver_account})."

    return True, None


def parse_date(date_str):
    """Parse date string to datetime object"""
    try:
        # Handle DD-MMM-YY format
        return datetime.strptime(date_str, '%d-%b-%y')
    except:
        try:
            # Handle DD MMM YYYY format (e.g., "30 Sep 2025")
            return datetime.strptime(date_str.strip(), '%d %b %Y')
        except:
            try:
                # Handle other common formats
                return datetime.strptime(date_str, '%d-%m-%y')
            except:
                return None


def extract_sender_name_from_description(description):
    """Extract sender name from bank description"""
    description = description.lower()
    
    # Common patterns in bank descriptions
    patterns = [
        'raast p2p fund transfer from ',
        'money received from ',
        'fund transfer from ',
        'received from '
    ]
    
    for pattern in patterns:
        if pattern in description:
            # Extract text after the pattern
            start_idx = description.index(pattern) + len(pattern)
            remaining = description[start_idx:]
            
            # Extract name until we hit account numbers or bank codes
            # Stop at first sequence of digits or uppercase letters that look like account/bank codes
            name_parts = []
            words = remaining.split()
            
            for word in words:
                # Stop if we hit what looks like account number or bank code
                if word.isupper() or word.isdigit() or len(word) > 15:
                    break
                # Stop if word contains numbers mixed with letters (like HBL14167...)
                if any(c.isdigit() for c in word) and any(c.isalpha() for c in word):
                    break
                name_parts.append(word)
            
            return ' '.join(name_parts).strip()
    
    return None


def extract_phone_from_description(description):
    """Extract 12-digit phone number from bank description"""
    # Look for 12-digit numbers (Pakistani format: 923xxxxxxxxx)
    match = re.search(r'\b(92\d{10})\b', description)
    if match:
        return match.group(1)
    return None


def extract_transaction_id_from_description(description):
    """Extract transaction ID from STAN field in description"""
    description_upper = description.upper()
    
    if 'STAN' in description_upper:
        # Find STAN and extract the number after it
        start_idx = description_upper.index('STAN')
        remaining = description[start_idx:]
        
        # Look for pattern STAN(number) or STAN number
        match = re.search(r'STAN\s*\(?\s*(\d+)\s*\)?', remaining, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def verify_transaction(extracted_data, bank_transactions_df):
    """Compare extracted data with bank transactions from database"""

    # First validate receiver
    is_valid, error_msg = validate_receiver(extracted_data)
    if not is_valid:
        return error_msg, None, 'wrong_receiver'

    # Extract fields
    extracted_amount = float(extracted_data.get('amount', 0))
    extracted_date = parse_date(extracted_data.get('date', ''))
    sender_name = extracted_data.get('sender_name', '').lower().strip()
    sender_account = extracted_data.get('sender_account', '')
    sender_phone = extracted_data.get('sender_phone', '')
    transaction_id = extracted_data.get('transaction_id', '')

    if extracted_date is None:
        return "⚠️ **Unable to parse date from transaction slip**", None, 'date_parse_error'

    # Search in bank transactions
    matches = []

    for idx, row in bank_transactions_df.iterrows():
        # Parse statement date (using value_date or booking_date)
        date_col = 'value_date' if pd.notna(row.get('value_date')) else 'booking_date'
        stmt_date = parse_date(str(row[date_col]))
        if stmt_date is None:
            continue

        # Parse statement amount (credit column for incoming transfers)
        try:
            credit_amount = row.get('credit', 0)
            if pd.isna(credit_amount) or credit_amount == '':
                continue
            stmt_amount = float(credit_amount)
        except:
            continue

        # REQUIRED: Check if amounts match
        amount_match = abs(stmt_amount - extracted_amount) < 0.01
        if not amount_match:
            continue  # Skip if amount doesn't match

        # REQUIRED: Check if dates match
        date_match = stmt_date.date() == extracted_date.date()
        if not date_match:
            continue  # Skip if date doesn't match

        # Extract and check sender name from description
        description = str(row.get('description', ''))
        stmt_sender_name = extract_sender_name_from_description(description)
        
        # REQUIRED: Strict name matching - names should be similar
        name_match = False
        if stmt_sender_name and sender_name:
            # Normalize both names
            stmt_name_normalized = stmt_sender_name.lower().strip()
            sender_name_normalized = sender_name.lower().strip()
            
            # Check if names match (allowing for some word variations)
            stmt_words = set(stmt_name_normalized.split())
            sender_words = set(sender_name_normalized.split())
            
            # At least 50% of words should match
            common_words = stmt_words.intersection(sender_words)
            if len(common_words) > 0 and len(common_words) >= len(sender_words) * 0.5:
                name_match = True
        
        if not name_match:
            continue  # Skip if name doesn't match

        # REQUIRED: Check sender account OR phone number
        account_match = False
        phone_match = False
        
        if sender_account:
            account_match = sender_account in description
        
        if sender_phone:
            stmt_phone = extract_phone_from_description(description)
            if stmt_phone and sender_phone in stmt_phone:
                phone_match = True
        
        if not account_match and not phone_match:
            continue  # Skip if neither account nor phone matches

        # OPTIONAL: Check transaction ID from STAN
        transaction_id_match = False
        stmt_transaction_id = extract_transaction_id_from_description(description)
        if transaction_id and stmt_transaction_id:
            if transaction_id in stmt_transaction_id:
                transaction_id_match = True

        # All required fields matched - this is a full match
        matches.append({
            'row': row,
            'amount_match': amount_match,
            'date_match': date_match,
            'name_match': name_match,
            'transaction_id_match': transaction_id_match,
            'account_match': account_match,
            'phone_match': phone_match,
            'stmt_sender_name': stmt_sender_name,
            'stmt_transaction_id': stmt_transaction_id,
            'stmt_phone': extract_phone_from_description(description)
        })

    # Return results
    if matches:
        match = matches[0]
        
        # Build identifier info
        identifier_info = []
        if match['account_match']:
            identifier_info.append(f"Account: ...{sender_account} ✓")
        if match['phone_match']:
            identifier_info.append(f"Phone: {sender_phone} ✓")
        
        identifier_str = " | ".join(identifier_info)
        tid_info = f"✓ Matched" if match['transaction_id_match'] else "Not verified (optional)"
        
        # Get date column value for display
        date_col = 'value_date' if pd.notna(match['row'].get('value_date')) else 'booking_date'
        date_value = match['row'][date_col]
        
        result = f"""
✅ **Transaction Verified Successfully**

**Extracted Information:**
- Amount: {extracted_amount}
- Date: {extracted_data.get('date')}
- Sender Name: {extracted_data.get('sender_name')}
- {identifier_str}
- Transaction ID: {transaction_id if transaction_id else 'N/A'} ({tid_info})

**vs**

**Bank Transaction Record:**
- Amount: {match['row']['credit']} ✓
- Date: {date_value} ✓
- Sender Name: {match['stmt_sender_name']} ✓
- Account/Phone: {"✓ Found" if (match['account_match'] or match['phone_match']) else ""}
- Transaction ID (STAN): {match['stmt_transaction_id'] if match['stmt_transaction_id'] else 'N/A'}
- Full Description: {str(match['row']['description'])[:150]}...

**All required fields verified successfully!**
"""
        return result, match['row'], 'verified'

    else:
        # No matches found - could be any required field missing
        result = f"""
❌ **Transaction Not Found in Statement**

**Extracted Information:**
- Amount: {extracted_amount}
- Date: {extracted_data.get('date')}
- Sender Name: {extracted_data.get('sender_name')}
- Sender Account: ...{sender_account if sender_account else 'N/A'}
- Sender Phone: {sender_phone if sender_phone else 'N/A'}
- Transaction ID: {transaction_id if transaction_id else 'N/A'}

**Required fields for verification:**
✓ Amount must match
✓ Date must match
✓ Sender name must match (at least 50% words)
✓ Sender account (last 4 digits) OR phone number (12 digits) must match

**Optional field:**
• Transaction ID (STAN) - helps confirm but not required

No transaction found matching ALL required criteria.
"""
        return result, None, 'not_found'


def save_verification_result(extracted_data, verification_result, status, matched_row=None):
    """Save verification result to verification_results table"""
    # Prepare data for insertion
    amount = float(extracted_data.get('amount', 0)) if extracted_data.get('amount') else None
    donor_name = extracted_data.get('sender_name', '')
    phone = extracted_data.get('sender_phone', '')
    date = extracted_data.get('date', '')
    transaction_id = extracted_data.get('transaction_id', '')
    department = None
    currency = 'PKR'
    payment_channel = 'Bank Transfer'
    
    # Calculate checks passed/failed
    checks_passed = 0
    checks_failed = 0
    
    if status == 'verified':
        checks_passed = 4  # Amount, Date, Name, Account/Phone
        if matched_row is not None:
            # Check if transaction ID matched (optional)
            stmt_transaction_id = extract_transaction_id_from_description(str(matched_row.get('description', '')))
            if transaction_id and stmt_transaction_id and transaction_id in stmt_transaction_id:
                checks_passed += 1
    elif status == 'wrong_receiver':
        checks_failed = 2
    elif status == 'date_parse_error':
        checks_failed = 1
    else:  # not_found
        checks_failed = 4
    
    gsheet_row = None
    if matched_row is not None:
        try:
            gsheet_row_value = matched_row.get('gsheet_row')
            if gsheet_row_value is not None and pd.notna(gsheet_row_value):
                gsheet_row = int(float(gsheet_row_value))
        except (KeyError, ValueError, TypeError):
            gsheet_row = None
    
    save_success, save_error, verification_id = db.insert_verification_result(
        amount=amount,
        donor_name=donor_name,
        date=date,
        transaction_id=transaction_id,
        status=status,
        department=department,
        currency=currency,
        payment_channel=payment_channel,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        gsheet_row=gsheet_row
    )
    
    if not save_success:
        return save_success, save_error, None, None
    
    return True, None, verification_id, gsheet_row


# Initialize configuration panel state
if 'config_panel_open' not in st.session_state:
    st.session_state.config_panel_open = False

# Configuration data loading (always needed for processing)
bank_df = None
error = None
service_account_path = sheet_sync.get_service_account_path()
service_account_exists = sheet_sync.credentials_available()

# Load bank transactions (needed for verification)
bank_df, error = db.load_bank_transactions(credit_only=True)

# Main UI Header with Configuration Button
header_col1, header_col2 = st.columns([0.92, 0.08])

with header_col1:
    st.title("🏦 Transaction Verification Service")
    st.markdown("Upload a transaction slip to verify it against bank transactions in database")

with header_col2:
    st.markdown("<br>", unsafe_allow_html=True)  # Add spacing to align with title
    button_label = "⚙️" if not st.session_state.config_panel_open else "✕"
    button_type = "primary" if st.session_state.config_panel_open else "secondary"
    if st.button(button_label, use_container_width=False, type=button_type, key="config_toggle"):
        st.session_state.config_panel_open = not st.session_state.config_panel_open
        st.rerun()

# Create layout with conditional sidebar
if st.session_state.config_panel_open:
    # Sidebar is open: main content + sidebar
    main_col, sidebar_col = st.columns([0.80, 0.20], gap="medium")
    
    with sidebar_col:
        st.markdown("---")
        st.header("⚙️ Configuration")
        
        st.subheader("🗓️ Google Sheet Sync")
        if last_sync_time:
            st.success(f"✓ Background sync active | Last sync: {last_sync_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        else:
            st.info("Background sync starting... (runs automatically every 2 minutes)")

        if st.button("🔁 Force Google Sheet Sync", use_container_width=True):
            current_sheet_id = sheet_sync.get_spreadsheet_id()
            current_worksheet = sheet_sync.get_worksheet_name()
            st.write(f"**Fetching from:** Spreadsheet ID: `{current_sheet_id}`, Worksheet: `{current_worksheet}`")
            with st.spinner("Syncing latest bank transactions from Google Sheet..."):
                synced, message = sheet_sync.sync_bank_transactions(force=True)
            if synced:
                st.success(message)
            else:
                st.warning(message)
            last_sync_time = db.get_last_sync_time()
            if last_sync_time:
                st.caption(f"Last sync: {last_sync_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        st.caption(f"Service account file: `{service_account_path}` {'✓' if service_account_exists else '⚠️ Missing'}")

        st.markdown("---")
        st.subheader("📊 Bank Transactions")

        if error:
            st.error(error)
        elif bank_df is not None and len(bank_df) > 0:
            st.success(f"✓ Loaded {len(bank_df)} transactions from database")

            # Show preview
            with st.expander("Preview Transactions"):
                st.dataframe(bank_df.head(), use_container_width=True)
        else:
            st.warning("⚠️ No transactions found in database")

        st.markdown("---")
        st.markdown("### Database Info:")
        st.code("""Transactions are loaded from:
- Table: bank_transactions
- Filter: credit > 0 (incoming transfers)
- Results saved to: verification_results
- Screenshot metadata stored in: screenshots
- Background auto-sync: runs automatically every 2 minutes when Streamlit app is running""")
    
    # Main content area (when sidebar is open)
    with main_col:
        # Create two columns for split layout
        col_left, col_right = st.columns([1, 1], gap="large")
        
        # LEFT COLUMN: Image Upload Section
        with col_left:
            st.header("📤 Upload Transaction Slip")
            st.markdown("---")
            
            # File uploader for transaction slip
            uploaded_file = st.file_uploader(
                "Choose an image file",
                type=['png', 'jpg', 'jpeg'],
                help="Upload a screenshot of the transaction slip",
                label_visibility="collapsed"
            )
            
            if uploaded_file:
                # Display uploaded image with constrained size
                image = Image.open(uploaded_file)
                # Calculate display width (max 400px or 80% of column width)
                max_width = 400
                st.image(image, caption="Uploaded Transaction Slip", width=max_width)
                
                # Store in session state for processing
                if 'current_image' not in st.session_state or st.session_state.get('current_file_name') != uploaded_file.name:
                    st.session_state.current_image = image
                    st.session_state.current_file = uploaded_file
                    st.session_state.current_file_name = uploaded_file.name
                    st.session_state.messages.append({
                        "role": "user",
                        "content": "🖼️ Uploaded transaction slip"
                    })
            else:
                st.info("👆 Upload a transaction slip screenshot to begin verification")
                # Clear current image state when no file is uploaded
                if 'current_image' in st.session_state:
                    del st.session_state.current_image
                    del st.session_state.current_file
                    del st.session_state.current_file_name

        # RIGHT COLUMN: Verification Results Section
        with col_right:
            st.header("📊 Verification Results")
            st.markdown("---")
            
            # Check if there's an image to process
            if 'current_image' in st.session_state and bank_df is not None and len(bank_df) > 0:
                image = st.session_state.current_image
                uploaded_file = st.session_state.current_file
                
                with st.spinner("🔍 Analyzing transaction slip..."):
                    # Configure Gemini
                    model = configure_gemini()

                    # Extract data from image
                    extracted_data, error = extract_transaction_data(model, image)

                    if error:
                        st.error(f"**❌ Extraction Error:**\n\n{error}")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": error
                        })
                    else:
                        # Show extracted data
                        st.subheader("📋 Extracted Data")
                        st.json(extracted_data)

                        # Verify transaction
                        with st.spinner("✓ Verifying against bank transactions..."):
                            result, matched_row, status = verify_transaction(extracted_data, bank_df)
                            
                            st.markdown("---")
                            st.subheader("🔍 Verification Result")
                            st.markdown(result)

                            # Save verification result to database
                            with st.spinner("💾 Saving verification result..."):
                                save_success, save_error, verification_id, gsheet_row = save_verification_result(
                                    extracted_data, result, status, matched_row
                                )
                                if save_success:
                                    st.success("✅ Verification result saved to database")

                                    with st.spinner("🗂️ Saving screenshot metadata..."):
                                        screenshot_success, screenshot_message = store_screenshot_for_verification(
                                            uploaded_file, verification_id, status, gsheet_row
                                        )
                                        if screenshot_success:
                                            st.info(f"📸 {screenshot_message}")
                                        else:
                                            st.warning(f"⚠️ Screenshot save issue: {screenshot_message}")
                                else:
                                    st.warning(f"⚠️ Could not save result: {save_error}")

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": result
                        })
                        
                        # Clear the current image state after processing
                        if 'current_image' in st.session_state:
                            del st.session_state.current_image
                            del st.session_state.current_file
                            del st.session_state.current_file_name
                            
            elif 'current_image' in st.session_state and (bank_df is None or len(bank_df) == 0):
                st.error("⚠️ **No bank transactions found in database.**\n\nPlease ensure the bank_transactions table has data. Use the sidebar to force a sync from Google Sheets.")
            else:
                st.info("👈 Upload a transaction slip in the left panel to see verification results here.")
                
                # Display recent chat messages if any
                if st.session_state.messages:
                    with st.expander("💬 Recent Activity", expanded=False):
                        for message in st.session_state.messages[-5:]:  # Show last 5 messages
                            role_icon = "👤" if message["role"] == "user" else "🤖"
                            st.markdown(f"{role_icon} **{message['role'].title()}:** {message['content'][:100]}...")
else:
    # Sidebar is closed: full width main content
    # Create two columns for split layout
    col_left, col_right = st.columns([1, 1], gap="large")
    
    # LEFT COLUMN: Image Upload Section
    with col_left:
        st.header("📤 Upload Transaction Slip")
        st.markdown("---")
        
        # File uploader for transaction slip
        uploaded_file = st.file_uploader(
            "Choose an image file",
            type=['png', 'jpg', 'jpeg'],
            help="Upload a screenshot of the transaction slip",
            label_visibility="collapsed"
        )
        
        if uploaded_file:
            # Display uploaded image with constrained size
            image = Image.open(uploaded_file)
            # Calculate display width (max 400px or 80% of column width)
            max_width = 400
            st.image(image, caption="Uploaded Transaction Slip", width=max_width)
            
            # Store in session state for processing
            if 'current_image' not in st.session_state or st.session_state.get('current_file_name') != uploaded_file.name:
                st.session_state.current_image = image
                st.session_state.current_file = uploaded_file
                st.session_state.current_file_name = uploaded_file.name
                st.session_state.messages.append({
                    "role": "user",
                    "content": "🖼️ Uploaded transaction slip"
                })
        else:
            st.info("👆 Upload a transaction slip screenshot to begin verification")
            # Clear current image state when no file is uploaded
            if 'current_image' in st.session_state:
                del st.session_state.current_image
                del st.session_state.current_file
                del st.session_state.current_file_name

    # RIGHT COLUMN: Verification Results Section
    with col_right:
        st.header("📊 Verification Results")
        st.markdown("---")
        
        # Check if there's an image to process
        if 'current_image' in st.session_state and bank_df is not None and len(bank_df) > 0:
            image = st.session_state.current_image
            uploaded_file = st.session_state.current_file
            
            with st.spinner("🔍 Analyzing transaction slip..."):
                # Configure Gemini
                model = configure_gemini()

                # Extract data from image
                extracted_data, error = extract_transaction_data(model, image)

                if error:
                    st.error(f"**❌ Extraction Error:**\n\n{error}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error
                    })
                else:
                    # Show extracted data
                    st.subheader("📋 Extracted Data")
                    st.json(extracted_data)

                    # Verify transaction
                    with st.spinner("✓ Verifying against bank transactions..."):
                        result, matched_row, status = verify_transaction(extracted_data, bank_df)
                        
                        st.markdown("---")
                        st.subheader("🔍 Verification Result")
                        st.markdown(result)

                        # Save verification result to database
                        with st.spinner("💾 Saving verification result..."):
                            save_success, save_error, verification_id, gsheet_row = save_verification_result(
                                extracted_data, result, status, matched_row
                            )
                            if save_success:
                                st.success("✅ Verification result saved to database")

                                with st.spinner("🗂️ Saving screenshot metadata..."):
                                    screenshot_success, screenshot_message = store_screenshot_for_verification(
                                        uploaded_file, verification_id, status, gsheet_row
                                    )
                                    if screenshot_success:
                                        st.info(f"📸 {screenshot_message}")
                                    else:
                                        st.warning(f"⚠️ Screenshot save issue: {screenshot_message}")
                            else:
                                st.warning(f"⚠️ Could not save result: {save_error}")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result
                    })
                    
                    # Clear the current image state after processing
                    if 'current_image' in st.session_state:
                        del st.session_state.current_image
                        del st.session_state.current_file
                        del st.session_state.current_file_name
                        
        elif 'current_image' in st.session_state and (bank_df is None or len(bank_df) == 0):
            st.error("⚠️ **No bank transactions found in database.**\n\nPlease ensure the bank_transactions table has data. Use the sidebar to force a sync from Google Sheets.")
        else:
            st.info("👈 Upload a transaction slip in the left panel to see verification results here.")
            
            # Display recent chat messages if any
            if st.session_state.messages:
                with st.expander("💬 Recent Activity", expanded=False):
                    for message in st.session_state.messages[-5:]:  # Show last 5 messages
                        role_icon = "👤" if message["role"] == "user" else "🤖"
                        st.markdown(f"{role_icon} **{message['role'].title()}:** {message['content'][:100]}...")

# Instructions
with st.expander("ℹ️ How to Use"):
    st.markdown("""
    ### Step-by-Step Guide:

    1. **Background Sync**: The app automatically syncs `bank_transactions` from Google Sheets every 2 minutes (only new rows are added). Use the **Force Sync** button if you need an immediate refresh.
    2. **Upload Transaction Slip**: Upload a screenshot of the transaction slip to verify
    3. **View Results**: The bot will automatically:
       - Extract transaction details using AI
       - Validate receiver is Al-khidmat Welfare Society (account ending in 2664)
       - Compare with bank transactions from database
       - Save verification result to `verification_results` table
       - Show verification result

    ### Verification Requirements:
    
    **Pre-Verification (Must Pass):**
    - ✓ Receiver must be "Al-Khidmat Welfare Society"
    - ✓ Receiver account must end with 2664
    
    **Required Fields (All Must Match):**
    - ✓ Amount (exact match)
    - ✓ Date (exact match)
    - ✓ Sender name (at least 50% word overlap)
    - ✓ Sender account (last 4 digits) OR Phone (12 digits)
    
    **Optional Field:**
    - • Transaction ID (STAN) - Provides additional confirmation
    
    ### Expected Results:
    - ✅ **Verified**: All required fields match - Result saved to `verification_results` table
    - ❌ **Not Found**: Transaction missing or required fields don't match - Result saved to `verification_results` table
    - ⛔ **Wrong Receiver**: Not sent to Al-Khidmat or wrong account
    
    ### Database Tables:
    - **bank_transactions**: Source of truth for bank transactions (automatically synced from Google Sheet every 2 minutes in the background, or via the "Force Google Sheet Sync" button). Make sure `google_cred.json` (or the file referenced by `GOOGLE_SERVICE_ACCOUNT_FILE`) is present so the sync can read the sheet.
    - **verification_results**: Stores all verification results
    - **screenshots**: Stores uploaded screenshot file paths, verification status, and related metadata
    """)

# Footer
st.markdown("---")
st.markdown("*Prototype for testing only - Not for production deployment*")