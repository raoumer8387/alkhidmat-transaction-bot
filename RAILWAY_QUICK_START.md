# Railway Quick Start Guide

## 🚀 Quick Deployment Steps

### 1. Create Railway Project & Database (5 minutes)

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your repository
3. Click **"+ New"** → **Database** → **Add PostgreSQL**
4. Railway automatically adds `DATABASE_URL` to your environment variables ✅

### 2. Set Environment Variables (2 minutes)

In Railway dashboard → Your service → **Variables** tab, add:

```
AUTHORIZATION_TOKEN=your_bearer_token
VALID_USER_ID=your_user_id
VALID_PASSWORD=your_password
ALLOWED_IPS=127.0.0.1,::1,your_trusted_ip
```

**Optional (for auto DB init):**
```
AUTO_INIT_DB=true
```

### 3. Initialize Database (Choose ONE method)

#### Method A: Auto-initialize (Easiest)
Set `AUTO_INIT_DB=true` in Railway variables. Schema will be created automatically on first startup.

#### Method B: Manual Migration (Recommended)
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and link project
railway login
railway link

# Run migration
railway run python migrations/run_migration.py
```

#### Method C: Quick Init Script
```bash
railway run python init_db.py
```

### 4. Verify Deployment

1. Check Railway logs for successful startup
2. Visit: `https://your-app.railway.app/health`
3. Should return: `{"status": "ok", "service": "meezan-webhook-api"}`

## 📋 Environment Variables Checklist

- [ ] `DATABASE_URL` (auto-added by Railway when you add PostgreSQL)
- [ ] `AUTHORIZATION_TOKEN`
- [ ] `VALID_USER_ID`
- [ ] `VALID_PASSWORD`
- [ ] `ALLOWED_IPS`
- [ ] `AUTO_INIT_DB` (optional, set to `true` for auto-initialization)

## 🔍 Troubleshooting

**Database not connecting?**
- Check `DATABASE_URL` exists in Railway variables
- Verify PostgreSQL service is running in Railway dashboard

**Migration failed?**
- Check Railway logs for error details
- Ensure `DATABASE_URL` is accessible
- Try running migration via Railway CLI

**App not starting?**
- Check `Procfile` exists: `web: uvicorn api:app --host 0.0.0.0 --port $PORT`
- Verify all dependencies in `requirements.txt`
- Check Railway deployment logs

## 📚 Full Documentation

See [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md) for detailed instructions.

## 🎯 What Happens Next?

1. Railway detects your Python app automatically
2. Installs dependencies from `requirements.txt`
3. Starts your app using the `Procfile`
4. Your app connects to PostgreSQL using `DATABASE_URL`
5. Database tables are created (via migration or auto-init)

That's it! Your API is now live on Railway. 🎉

