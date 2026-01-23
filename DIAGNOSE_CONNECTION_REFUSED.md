# Diagnosing "Connection Refused" After Successful Startup

If your Railway logs show the app started successfully but you're still getting "connection refused" errors, follow these steps:

## 🔍 Step 1: Verify App is Actually Running

Check Railway logs for these signs:

### ✅ Good Signs:
```
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
[Startup] Server is ready to accept connections
```

### ❌ Bad Signs:
- App crashes immediately after startup
- Port binding errors
- Import errors after startup
- No "Uvicorn running" message

## 🔍 Step 2: Check for Crashes After Startup

Look for error messages AFTER the startup completes:
- Check if there are any exceptions in the logs
- Look for "Process exited" or "Container stopped" messages
- Check if the app is restarting repeatedly

## 🔍 Step 3: Verify Port Configuration

Your logs show: `Uvicorn running on http://0.0.0.0:8080`

This means Railway set `PORT=8080`. Verify:

1. **Check Railway Variables:**
   - Go to Railway dashboard → Your service → Variables
   - Look for `PORT` variable (Railway sets this automatically)
   - It should match the port in your logs

2. **Verify Procfile:**
   ```
   web: uvicorn api:app --host 0.0.0.0 --port $PORT
   ```
   - Must use `$PORT` (not a hardcoded number)
   - Must bind to `0.0.0.0` (not `127.0.0.1`)

## 🔍 Step 4: Check Railway Health Check Configuration

Railway might be checking health before the app is ready:

1. **Check Railway Service Settings:**
   - Go to Railway dashboard → Your service → Settings
   - Look for "Health Check" or "Health Check Path"
   - Default should be `/` or `/health`
   - Make sure it matches an endpoint that exists

2. **Verify Health Endpoint Works:**
   - The `/health` endpoint should be accessible without authentication
   - It should return a 200 status code
   - Check Railway logs for any errors when `/health` is hit

## 🔍 Step 5: Check Request Logs

With the new logging middleware, you should see:
```
[Request] GET /health from <ip>
[Request] GET /health - 200 (0.001s)
```

If you DON'T see these logs, Railway isn't reaching your app.

## 🔍 Step 6: Check Railway Service Status

1. **Go to Railway Dashboard:**
   - Your service → Overview
   - Check if status shows "Active" or "Deploying"
   - If it shows "Failed" or "Crashed", check the error message

2. **Check Deployment Status:**
   - Go to Deployments tab
   - Check the latest deployment status
   - Look for any error indicators

## 🔍 Step 7: Test Locally with Same Configuration

To verify the app works:

1. **Set environment variables locally:**
   ```bash
   export PORT=8080
   export DATABASE_URL="your_railway_db_url"
   export AUTHORIZATION_TOKEN="your_token"
   export VALID_USER_ID="your_user_id"
   export VALID_PASSWORD="your_password"
   export ALLOWED_IPS="127.0.0.1,::1"
   ```

2. **Run locally:**
   ```bash
   uvicorn api:app --host 0.0.0.0 --port 8080
   ```

3. **Test health endpoint:**
   ```bash
   curl http://localhost:8080/health
   ```

If this works locally, the issue is Railway-specific.

## 🔍 Step 8: Check Railway-Specific Issues

### Issue: Multiple Deployments
- Railway might be deploying multiple instances
- Check if you have multiple deployments running
- The "connection refused" might be from an old deployment

**Fix:** Wait for the latest deployment to fully complete, or manually stop old deployments.

### Issue: Health Check Timing
- Railway might check health before app is ready
- Health checks might be too aggressive

**Fix:** Railway should wait for the app to start. If not, contact Railway support.

### Issue: Network/Routing
- Railway's load balancer might not be routing correctly
- There might be a networking issue

**Fix:** Try redeploying or contact Railway support.

## 🔍 Step 9: Enable Verbose Logging

Add this to see more details:

In Railway dashboard → Your service → Variables, add:
```
LOG_LEVEL=DEBUG
```

Then check logs for more detailed information.

## 🔍 Step 10: Check Railway Status Page

1. Visit: https://status.railway.app
2. Check if there are any ongoing incidents
3. Railway might be experiencing issues

## 🚀 Quick Fixes to Try

### Fix 1: Redeploy
1. Railway dashboard → Your service
2. Click "Redeploy" button
3. Wait for deployment to complete
4. Check logs again

### Fix 2: Restart Service
1. Railway dashboard → Your service
2. Click "Settings" → "Restart"
3. Wait for restart
4. Check logs

### Fix 3: Check Recent Code Changes
- Did you recently push code changes?
- Are there any syntax errors?
- Did you add any new dependencies?

### Fix 4: Verify Database Connection
- Is PostgreSQL service running?
- Is `DATABASE_URL` set correctly?
- Can the app connect to the database?

## 📋 What to Share with Railway Support

If none of the above works, gather this information:

1. **Railway Logs:**
   - Copy the last 100 lines of logs
   - Include startup messages and any errors

2. **Deployment Details:**
   - Deployment ID
   - Deployment timestamp
   - Service name

3. **Configuration:**
   - Procfile contents
   - Environment variables (mask sensitive values)
   - Railway plan (Free/Hobby/Pro)

4. **Error Details:**
   - Exact error message from Railway dashboard
   - When the error occurs (on startup, on request, etc.)
   - Any patterns you notice

## 💡 Most Likely Causes

Based on your logs showing successful startup but "connection refused":

1. **Timing Issue:** Railway health check happens before app is ready
   - **Solution:** Wait a few seconds after deployment, then test

2. **Port Mismatch:** App binding to wrong port
   - **Solution:** Verify `$PORT` is being used correctly

3. **App Crashes After Startup:** App starts but crashes on first request
   - **Solution:** Check logs for errors after startup messages

4. **Network Routing:** Railway load balancer routing issue
   - **Solution:** Redeploy or contact Railway support

## ✅ Success Indicators

Your app is working correctly when you see:

1. **In Logs:**
   ```
   [Request] GET /health from <ip>
   [Request] GET /health - 200 (0.001s)
   ```

2. **In Browser:**
   - Visiting `/health` returns JSON response
   - Status code is 200
   - No 502 errors

3. **In Railway Dashboard:**
   - Service status shows "Active"
   - No error indicators
   - Deployment shows "Success"




