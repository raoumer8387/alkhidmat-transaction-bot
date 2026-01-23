# Fixing Railway Database Connection Issue

## Problem
You're getting: `could not translate host name "postgres.railway.internal" to address`

This happens when the database service isn't properly linked to your web service.

## ✅ Solution: Link Database Service (Recommended)

**Railway should automatically provide `DATABASE_URL` when services are linked. Don't manually copy it!**

### Step 1: Link PostgreSQL to Your Web Service

1. **Go to Railway Dashboard:**
   - Open your project
   - You should see both services:
     - Your web service (FastAPI app)
     - PostgreSQL service

2. **Link the Database:**
   - Click on your **PostgreSQL service**
   - Go to **"Settings"** tab
   - Look for **"Connect"** or **"Variables"** section
   - You should see `DATABASE_URL` listed
   - Make sure it's **shared** with your web service

3. **Or Link from Web Service:**
   - Click on your **web service** (FastAPI app)
   - Go to **"Variables"** tab
   - Look for **"Add Reference"** or **"Link Service"** button
   - Select your PostgreSQL service
   - Railway will automatically add `DATABASE_URL`

### Step 2: Verify DATABASE_URL is Set

1. Go to your **web service** → **Variables** tab
2. Look for `DATABASE_URL`
3. It should be there automatically (don't manually add it)
4. The format should be: `postgresql://postgres:password@hostname:port/railway`
   - The hostname should be something like `containers-us-west-xxx.railway.app` (NOT `postgres.railway.internal`)

### Step 3: Remove Manually Added DATABASE_URL (If You Added One)

If you manually added `DATABASE_URL`:
1. Go to your web service → Variables
2. Find `DATABASE_URL`
3. **Delete it** (Railway will provide the correct one automatically)
4. Make sure the PostgreSQL service is linked instead

### Step 4: Redeploy

After linking:
1. Railway will automatically redeploy
2. Or manually: Service → **Redeploy**
3. Check logs to verify connection works

## 🔍 Alternative: Use Public Connection String

If linking doesn't work, you can use the public connection string:

1. **Get Public Connection String:**
   - Go to PostgreSQL service → **Connect** tab
   - Look for **"Public Network"** connection string
   - Copy that (it will have a public hostname, not `.internal`)

2. **Set in Web Service:**
   - Go to web service → Variables
   - Add `DATABASE_URL` with the public connection string
   - Format: `postgresql://postgres:password@public-hostname.railway.app:port/railway`

## ✅ Verify It's Working

After fixing, check `/health` endpoint:
```bash
curl https://alkhidmat-transaction-bot-production.up.railway.app/health
```

You should see:
```json
{
  "status": "ok",
  "service": "meezan-webhook-api",
  "configured": true,
  "missing_vars": [],
  "database": "connected"
}
```

## 🚨 Important Notes

1. **Don't manually copy DATABASE_URL** - Railway provides it automatically when services are linked
2. **`.internal` hostnames** only work when services are in the same Railway project and properly linked
3. **Public connection strings** work from anywhere but may have connection limits
4. **Railway automatically manages** `DATABASE_URL` - you shouldn't need to set it manually

## 📋 Quick Checklist

- [ ] PostgreSQL service exists in Railway project
- [ ] Web service exists in Railway project  
- [ ] Services are linked (DATABASE_URL appears automatically)
- [ ] No manually added DATABASE_URL (let Railway provide it)
- [ ] Service redeployed after linking
- [ ] `/health` endpoint shows `"database": "connected"`




