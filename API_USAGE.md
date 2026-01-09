# API Usage Guide - Railway Deployment

This guide explains how to use the FastAPI endpoints after deploying to Railway.

## 🚀 Getting Your Railway URL

1. Go to your Railway project dashboard
2. Click on your deployed service
3. Find the **"Public Domain"** or **"Generate Domain"** section
4. Your URL will look like: `https://your-app-name.up.railway.app`

**Note:** Railway provides a public URL automatically. You can also set up a custom domain if needed.

---

## 📋 Required Environment Variables in Railway

Make sure these are set in your Railway project settings:

- `AUTHORIZATION_TOKEN` - Bearer token for API authentication
- `VALID_USER_ID` - User ID for `/meezan-alert` endpoint
- `VALID_PASSWORD` - Password for `/meezan-alert` endpoint
- `ALLOWED_IPS` - (Optional) Comma-separated list of allowed IP addresses (defaults to localhost)

**To set environment variables in Railway:**
1. Go to your service → Variables tab
2. Add each variable with its value
3. Redeploy if needed

---

## 🔌 Available Endpoints

### 1. Health Check (GET)

**Endpoint:** `GET /health`

**Description:** Simple health check to verify the API is running.

**Authentication:** None required

**Example Request (curl):**
```bash
curl https://your-app-name.up.railway.app/health
```

**Example Request (Python):**
```python
import requests

url = "https://your-app-name.up.railway.app/health"
response = requests.get(url)
print(response.json())
# Output: {"status": "ok", "service": "meezan-webhook-api"}
```

---

### 2. Meezan Bank Alert (POST)

**Endpoint:** `POST /meezan-alert`

**Description:** Receives transaction alerts from Meezan Bank webhook.

**Authentication Required:**
- **Bearer Token** in `Authorization` header
- **userID** and **password** in request body

**Request Headers:**
```
Authorization: Bearer YOUR_AUTHORIZATION_TOKEN
Content-Type: application/json
```

**Request Body:**
```json
{
  "userID": "your_user_id",
  "password": "your_password",
  "channelType": "optional",
  "channelSubType": "optional",
  "transactionDateTime": "2025-10-02T18:08:54",
  "hostData": {
    "messageData": "02-OCT-25,180854, Mehmood Distributor, 29052, MTDOW,904446,0101, PNSC Branch, 560000.00",
    "id": "unique_doc_id_12345"
  }
}
```

**Example Request (curl):**
```bash
curl -X POST https://your-app-name.up.railway.app/meezan-alert \
  -H "Authorization: Bearer YOUR_AUTHORIZATION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "userID": "your_user_id",
    "password": "your_password",
    "transactionDateTime": "2025-10-02T18:08:54",
    "hostData": {
      "messageData": "02-OCT-25,180854, Mehmood Distributor, 29052, MTDOW,904446,0101, PNSC Branch, 560000.00",
      "id": "doc_12345"
    }
  }'
```

**Example Request (Python):**
```python
import requests

url = "https://your-app-name.up.railway.app/meezan-alert"
headers = {
    "Authorization": "Bearer YOUR_AUTHORIZATION_TOKEN",
    "Content-Type": "application/json"
}
payload = {
    "userID": "your_user_id",
    "password": "your_password",
    "transactionDateTime": "2025-10-02T18:08:54",
    "hostData": {
        "messageData": "02-OCT-25,180854, Mehmood Distributor, 29052, MTDOW,904446,0101, PNSC Branch, 560000.00",
        "id": "doc_12345"
    }
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

**Success Response (200):**
```json
{
  "statusCode": "00",
  "statusDesc": "success",
  "id": "doc_12345",
  "stan": "generated-uuid-here"
}
```

**Error Response (200):**
```json
{
  "statusCode": "01",
  "statusDesc": "fail",
  "id": "doc_12345",
  "stan": "existing-stan-if-duplicate"
}
```

**Important Notes:**
- The endpoint processes transactions in the background
- Returns immediately with success response
- Duplicate `doc_id` values will return statusCode "01" with existing STAN
- IP whitelist check is performed (make sure your bank's IP is in `ALLOWED_IPS`)

---

### 3. Upload Evidence (POST)

**Endpoint:** `POST /upload-evidence`

**Description:** Uploads evidence files (screenshots, PDFs) for donation verification.

**Authentication:** None required

**Request Format:** `multipart/form-data`

**Form Fields:**
- `file`: The file to upload (JPEG, PNG, or PDF)
- `donation_id`: Unique donation identifier

**Example Request (curl):**
```bash
curl -X POST https://your-app-name.up.railway.app/upload-evidence \
  -F "file=@/path/to/your/screenshot.jpg" \
  -F "donation_id=DON12345"
```

**Example Request (Python):**
```python
import requests

url = "https://your-app-name.up.railway.app/upload-evidence"

with open("screenshot.jpg", "rb") as f:
    files = {"file": ("screenshot.jpg", f, "image/jpeg")}
    data = {"donation_id": "DON12345"}
    
    response = requests.post(url, files=files, data=data)
    print(response.json())
```

**Success Response (200):**
```json
{
  "status": "ok",
  "message": "File uploaded successfully",
  "screenshot_id": 123,
  "file_path": "/absolute/path/to/file.jpg"
}
```

**Error Response (200 - Duplicate):**
```json
{
  "status": "error",
  "message": "donation_id 'DON12345' already exists"
}
```

**Important Notes:**
- Files are saved to `uploads/` directory
- Filename is generated as: `{donation_id}_{uuid}.{extension}`
- Duplicate `donation_id` values will return an error

---

## 🧪 Testing Your Deployment

### Quick Test Script (Python)

Create a file `test_api.py`:

```python
import requests
import os

# Replace with your Railway URL
BASE_URL = "https://your-app-name.up.railway.app"

# Replace with your credentials
AUTH_TOKEN = os.getenv("AUTHORIZATION_TOKEN", "your_token_here")
USER_ID = os.getenv("VALID_USER_ID", "your_user_id")
PASSWORD = os.getenv("VALID_PASSWORD", "your_password")

def test_health():
    """Test health check endpoint"""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

def test_meezan_alert():
    """Test meezan alert endpoint"""
    print("Testing /meezan-alert endpoint...")
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "userID": USER_ID,
        "password": PASSWORD,
        "transactionDateTime": "2025-10-02T18:08:54",
        "hostData": {
            "messageData": "02-OCT-25,180854, Test User, 29052, MTDOW,904446,0101, Test Branch, 1000.00",
            "id": f"test_doc_{os.urandom(4).hex()}"
        }
    }
    response = requests.post(f"{BASE_URL}/meezan-alert", json=payload, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

if __name__ == "__main__":
    test_health()
    test_meezan_alert()
```

Run it:
```bash
python test_api.py
```

---

## 🔒 Security Considerations

1. **IP Whitelist**: For production, add your bank's IP addresses to `ALLOWED_IPS` in Railway environment variables
2. **Bearer Token**: Keep your `AUTHORIZATION_TOKEN` secure and never commit it to Git
3. **Credentials**: Store `VALID_USER_ID` and `VALID_PASSWORD` securely in Railway environment variables
4. **HTTPS**: Railway provides HTTPS by default - always use `https://` URLs

---

## 📝 Common Issues & Solutions

### Issue: 403 Forbidden (IP not whitelisted)
**Solution:** Add your IP address to `ALLOWED_IPS` environment variable in Railway

### Issue: 401 Unauthorized
**Solution:** Check that:
- Bearer token is correct in `Authorization` header
- `userID` and `password` match environment variables
- Header format is: `Authorization: Bearer YOUR_TOKEN`

### Issue: Endpoint not found (404)
**Solution:** 
- Verify the Railway URL is correct
- Check that the service is deployed and running
- Ensure you're using the correct endpoint path (`/meezan-alert`, not `/meezan-alert/`)

### Issue: Connection timeout
**Solution:**
- Check Railway service logs
- Verify the service is running (check Railway dashboard)
- Ensure your Railway service has sufficient resources

---

## 📚 Additional Resources

- **Railway Docs**: https://docs.railway.app
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **API Interactive Docs**: Visit `https://your-app-name.up.railway.app/docs` for Swagger UI (if enabled)

---

## 🔗 Quick Reference

| Endpoint | Method | Auth Required | Purpose |
|----------|--------|---------------|---------|
| `/health` | GET | No | Health check |
| `/meezan-alert` | POST | Yes (Bearer + userID/password) | Receive bank transaction alerts |
| `/upload-evidence` | POST | No | Upload evidence files |

---

**Need Help?** Check Railway logs in your dashboard for detailed error messages.

