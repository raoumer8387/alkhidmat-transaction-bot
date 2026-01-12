# Railway Deployment Guide

This guide will help you deploy your FastAPI application to Railway and set up a PostgreSQL database.

## Prerequisites

- A Railway account (sign up at [railway.app](https://railway.app))
- Your code pushed to a GitHub repository
- Basic understanding of environment variables

## Step 1: Create a Railway Project

1. Go to [railway.app](https://railway.app) and sign in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository
5. Railway will automatically detect it's a Python application

## Step 2: Add PostgreSQL Database

1. In your Railway project dashboard, click **"+ New"**
2. Select **"Database"** → **"Add PostgreSQL"**
3. Railway will automatically create a PostgreSQL database
4. The `DATABASE_URL` environment variable will be automatically added to your project

## Step 3: Configure Environment Variables

In your Railway project dashboard:

1. Go to your **service** (the web app, not the database)
2. Click on the **"Variables"** tab
3. Add the following environment variables:

### Required Environment Variables:

```
AUTHORIZATION_TOKEN=your_bearer_token_here
VALID_USER_ID=your_user_id_here
VALID_PASSWORD=your_password_here
ALLOWED_IPS=127.0.0.1,::1,your_trusted_ip_here
```

**Note:** `DATABASE_URL` is automatically provided by Railway when you add the PostgreSQL service. You don't need to set it manually.

### How to Set Environment Variables:

1. Click **"+ New Variable"**
2. Enter the variable name (e.g., `AUTHORIZATION_TOKEN`)
3. Enter the variable value
4. Click **"Add"**
5. Repeat for all required variables

## Step 4: Run Database Migrations

After deploying, you need to create the database tables. You have two options:

### Option A: Run Migration Script via Railway CLI (Recommended)

1. Install Railway CLI:
   ```bash
   npm i -g @railway/cli
   ```

2. Login to Railway:
   ```bash
   railway login
   ```

3. Link your project:
   ```bash
   railway link
   ```

4. Run the migration:
   ```bash
   railway run python migrations/run_migration.py
   ```

### Option B: Run Migration via Railway Dashboard

1. Go to your Railway project dashboard
2. Click on your **web service**
3. Go to **"Deployments"** tab
4. Click on the latest deployment
5. Click **"View Logs"**
6. Use the **"Shell"** button to open a shell
7. Run:
   ```bash
   python migrations/run_migration.py
   ```

### Option C: Initialize Schema via Application Code

The application can also initialize the schema automatically. You can add a startup event to your FastAPI app:

```python
@app.on_event("startup")
async def startup_event():
    db.initialize_schema()
```

**Note:** The migration script (`migrations/run_migration.py`) will automatically use the `DATABASE_URL` environment variable provided by Railway.

## Step 5: Verify Deployment

1. Check your deployment logs in Railway dashboard
2. Visit your Railway-provided URL (e.g., `https://your-app.railway.app`)
3. Test the health endpoint: `https://your-app.railway.app/health`
4. You should see: `{"status": "ok", "service": "meezan-webhook-api"}`

## Step 6: Configure Custom Domain (Optional)

1. In Railway dashboard, go to your service
2. Click **"Settings"** → **"Networking"**
3. Click **"Generate Domain"** or add your custom domain
4. Railway will provide an HTTPS certificate automatically

## Database Connection Details

Railway automatically provides the `DATABASE_URL` environment variable in this format:
```
postgresql://postgres:password@hostname:port/railway
```

Your application code in `db.py` already handles this automatically:
- It checks for `DATABASE_URL` first (Railway format)
- Falls back to individual `DB_*` variables if `DATABASE_URL` is not set

## Troubleshooting

### Database Connection Issues

1. **Check if DATABASE_URL is set:**
   - Go to Railway dashboard → Your service → Variables
   - Ensure `DATABASE_URL` exists (it's added automatically when you add PostgreSQL)

2. **Verify database is running:**
   - In Railway dashboard, check your PostgreSQL service status
   - It should show "Active"

3. **Check connection string format:**
   - Railway uses `postgres://` which gets converted to `postgresql://` automatically
   - Your `db.py` handles this conversion

### Migration Issues

1. **If migration fails:**
   - Check Railway logs for error messages
   - Ensure `DATABASE_URL` is accessible
   - Verify the migration script has correct permissions

2. **If tables already exist:**
   - The migration uses `CREATE TABLE IF NOT EXISTS`, so it's safe to run multiple times
   - You can run it again without issues

### Application Not Starting

1. **Check Procfile:**
   - Ensure `Procfile` exists with: `web: uvicorn api:app --host 0.0.0.0 --port $PORT`
   - Railway uses this to start your application

2. **Check requirements.txt:**
   - Ensure all dependencies are listed
   - Railway installs dependencies automatically

3. **Check logs:**
   - Go to Railway dashboard → Your service → Deployments → View Logs
   - Look for error messages

## File Storage Note

⚠️ **Important:** The `/upload-evidence` endpoint saves files to the `uploads/` directory. 

**Railway's filesystem is ephemeral** - files will be lost when the service restarts or redeploys. For production, consider:

1. **Use Railway Volumes** (persistent storage):
   - Add a Volume in Railway dashboard
   - Mount it to your service
   - Update file paths to use the volume

2. **Use Cloud Storage** (recommended):
   - AWS S3
   - Google Cloud Storage
   - Cloudinary
   - Railway's built-in storage options

## Monitoring

Railway provides:
- **Logs:** Real-time application logs
- **Metrics:** CPU, Memory, Network usage
- **Deployments:** History of all deployments

Access these from your Railway project dashboard.

## Cost Considerations

Railway offers:
- **Free tier:** $5 credit/month
- **Hobby plan:** $5/month + usage
- **Pro plan:** $20/month + usage

PostgreSQL database usage counts toward your usage. Check Railway pricing for details.

## Support

- Railway Documentation: [docs.railway.app](https://docs.railway.app)
- Railway Discord: [discord.gg/railway](https://discord.gg/railway)
- Railway Status: [status.railway.app](https://status.railway.app)

## Quick Checklist

- [ ] Created Railway project
- [ ] Connected GitHub repository
- [ ] Added PostgreSQL database
- [ ] Set all required environment variables
- [ ] Ran database migrations
- [ ] Verified health endpoint works
- [ ] Tested webhook endpoint
- [ ] Configured custom domain (optional)
- [ ] Set up file storage solution (if using uploads)

