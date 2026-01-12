# Troubleshooting 502 Bad Gateway Error on Railway

A 502 error means your application crashed or failed to start. Here's how to diagnose and fix it.

## 🔍 Step 1: Check Railway Logs

**This is the most important step!**

1. Go to Railway dashboard → Your service
2. Click **"Deployments"** tab
3. Click on the latest deployment
4. Click **"View Logs"**
5. Look for error messages (usually in red)

Common error patterns to look for:
- `ValueError: Missing required environment variables`
- `ModuleNotFoundError` or `ImportError`
- `Database connection failed`
- `Port already in use`
- `SyntaxError` or `IndentationError`

## 🚨 Common Causes & Fixes

### 1. Missing Environment Variables (Most Common)

**Error in logs:**
```
ValueError: Missing required environment variables: AUTHORIZATION_TOKEN, VALID_USER_ID
```

**Fix:**
1. Go to Railway dashboard → Your service → **Variables** tab
2. Add these required variables:
   - `AUTHORIZATION_TOKEN` (your bearer token)
   - `VALID_USER_ID` (your user ID)
   - `VALID_PASSWORD` (your password)
   - `ALLOWED_IPS` (comma-separated IPs, e.g., `127.0.0.1,::1`)
3. Redeploy (Railway auto-redeploys when you add variables)

### 2. Database Connection Issues

**Error in logs:**
```
psycopg2.OperationalError: could not connect to server
```

**Fix:**
1. Verify PostgreSQL service is running in Railway dashboard
2. Check that `DATABASE_URL` exists in your service variables
   - Railway adds this automatically when you create PostgreSQL
   - If missing, you may need to link the database to your service
3. In Railway dashboard:
   - Go to your PostgreSQL service
   - Click **"Connect"** tab
   - Copy the connection string
   - Go to your web service → Variables
   - Add `DATABASE_URL` with the copied value

### 3. Port Configuration Issue

**Error in logs:**
```
Address already in use
```

**Fix:**
- Your `Procfile` should be: `web: uvicorn api:app --host 0.0.0.0 --port $PORT`
- Railway automatically sets `$PORT` - don't hardcode it
- Make sure you're using `$PORT` not a fixed number

### 4. Missing Dependencies

**Error in logs:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Fix:**
1. Check `requirements.txt` includes all dependencies
2. Verify Railway is installing dependencies (check build logs)
3. Make sure `requirements.txt` is in the root directory

### 5. Python Version Mismatch

**Error in logs:**
```
Python version not supported
```

**Fix:**
1. Check `runtime.txt` exists with: `python-3.12.7` (or your Python version)
2. Or Railway will auto-detect from your code

### 6. Import Errors

**Error in logs:**
```
ImportError: cannot import name 'X' from 'Y'
```

**Fix:**
- Check your code for circular imports
- Verify all imported modules exist
- Check file paths are correct

## 🔧 Quick Diagnostic Steps

### Check 1: Verify Environment Variables

Run this in Railway shell (or via CLI):
```bash
railway run python -c "import os; print('AUTHORIZATION_TOKEN:', 'SET' if os.getenv('AUTHORIZATION_TOKEN') else 'MISSING'); print('VALID_USER_ID:', 'SET' if os.getenv('VALID_USER_ID') else 'MISSING'); print('VALID_PASSWORD:', 'SET' if os.getenv('VALID_PASSWORD') else 'MISSING'); print('DATABASE_URL:', 'SET' if os.getenv('DATABASE_URL') else 'MISSING')"
```

### Check 2: Test Database Connection

```bash
railway run python -c "import db; conn = db.get_connection(); print('✅ Database connected'); conn.close()"
```

### Check 3: Test Application Import

```bash
railway run python -c "import api; print('✅ Application imports successfully')"
```

## 📋 Pre-Deployment Checklist

Before deploying, ensure:

- [ ] All environment variables are set in Railway
- [ ] `Procfile` exists and is correct
- [ ] `requirements.txt` has all dependencies
- [ ] `DATABASE_URL` is set (or PostgreSQL is linked)
- [ ] Database tables are created (run migration)
- [ ] No syntax errors in your code
- [ ] Application can start locally with same env vars

## 🛠️ How to View Real-Time Logs

**Via Railway Dashboard:**
1. Go to your service
2. Click **"Deployments"** → Latest deployment
3. Click **"View Logs"**
4. Logs update in real-time

**Via Railway CLI:**
```bash
railway logs --follow
```

## 🚀 After Fixing

1. **Redeploy:**
   - Railway auto-redeploys when you:
     - Push to GitHub (if connected)
     - Add/modify environment variables
   - Or manually: Railway dashboard → Service → **"Redeploy"**

2. **Verify:**
   - Check logs show: `✅ Application startup complete`
   - Visit: `https://your-app.railway.app/health`
   - Should return: `{"status": "ok", "service": "meezan-webhook-api"}`

## 💡 Pro Tips

1. **Always check logs first** - they tell you exactly what's wrong
2. **Test locally first** - if it works locally with same env vars, it should work on Railway
3. **Use Railway CLI** - easier to debug: `railway run python your_script.py`
4. **Check build logs** - sometimes the issue is during dependency installation

## 📞 Still Having Issues?

1. **Check Railway Status:** [status.railway.app](https://status.railway.app)
2. **Railway Discord:** [discord.gg/railway](https://discord.gg/railway)
3. **Railway Docs:** [docs.railway.app](https://docs.railway.app)

## 🔍 Example Log Output (Success)

```
[Startup] Loading environment variables...
[Startup] ✅ All required environment variables are set
[Startup] Database auto-initialization disabled (set AUTO_INIT_DB=true to enable)
[Startup] ✅ Application startup complete
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:PORT (Press CTRL+C to quit)
```

## 🔍 Example Log Output (Failure)

```
[Startup] Loading environment variables...
[Startup] ❌ ERROR: Missing required environment variables: AUTHORIZATION_TOKEN, VALID_USER_ID
[Startup] Please set these variables in Railway dashboard → Your service → Variables
[Startup] Application will not start until these are configured.
ValueError: Missing required environment variables: AUTHORIZATION_TOKEN, VALID_USER_ID
```

This tells you exactly what's missing!

