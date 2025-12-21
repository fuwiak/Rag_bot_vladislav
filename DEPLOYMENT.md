# Railway Deployment Guide

This project has been configured to deploy securely on Railway with all credentials stored in Railway environment variables (not in code or Docker images).

## Changes Made

### 1. Docker Configuration
- ✅ Updated `backend/.dockerignore` to exclude all `.env` files and credentials
- ✅ Created `admin-panel/.dockerignore` to exclude `.env` files
- ✅ Updated Dockerfiles to use `PORT` environment variable (Railway provides this)
- ✅ Created `docker-compose.yml` for production (without `env_file`)

### 2. Application Configuration
- ✅ Updated `backend/app/core/config.py` to make `.env` file optional
  - Now reads only from environment variables
  - `.env` file is optional for local development
  - Added validator for `CORS_ORIGINS` to parse comma-separated strings
- ✅ Updated `admin-panel/next.config.js` to use `NEXT_PUBLIC_*` prefix for client-side env vars
- ✅ Updated `docker-compose.local.yml` with comments about Railway deployment

### 3. Railway Configuration
- ✅ Updated `railway.json` with deployment notes
- ✅ Created `RAILWAY_ENV_VARS.md` with complete list of required environment variables

## Deployment Steps

### 1. Create Railway Services

1. **Backend Service:**
   - Create a new service in Railway
   - Connect your GitHub repository
   - Set root directory to project root
   - Railway will detect `railway.json` or use `backend/Dockerfile`

2. **Admin Panel Service (optional, if deploying separately):**
   - Create another service
   - Set Dockerfile path to `admin-panel/Dockerfile`
   - Set port to 3000 (or use `ADMIN_PANEL_PORT` env var)

3. **PostgreSQL Service (REQUIRED):**
   - Click "+ New" → "Database" → "Add PostgreSQL"
   - Railway will automatically create PostgreSQL service and provide `DATABASE_URL`
   - The `DATABASE_URL` will be automatically available to your backend service
   - See `RAILWAY_POSTGRES_SETUP.md` for detailed step-by-step instructions

### 2. Set Environment Variables

Go to each service's "Variables" tab and add all required variables (see `RAILWAY_ENV_VARS.md`):

**Backend Service:**
- `DATABASE_URL` (auto-provided if using Railway PostgreSQL)
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `OPENROUTER_API_KEY`
- `ADMIN_SECRET_KEY` (generate with `openssl rand -hex 32`)
- `ADMIN_SESSION_SECRET` (generate with `openssl rand -hex 32`)
- `APP_URL` (your admin panel URL)
- `BACKEND_URL` (your backend URL)
- `CORS_ORIGINS` (comma-separated, e.g., `https://admin.railway.app,https://api.railway.app`)

**Admin Panel Service:**
- `NEXT_PUBLIC_BACKEND_URL` (your backend URL)

### 3. Deploy

Railway will automatically deploy when you:
- Push to the connected branch
- Manually trigger a deployment
- Update environment variables

## Local Development

For local development, you can still use `.env` files:

1. Create `.env` in the project root
2. Add the same variables as above
3. Run `docker-compose -f docker-compose.local.yml up`

**Note:** `.env` files are:
- ✅ Excluded from Git (in `.gitignore`)
- ✅ Excluded from Docker builds (in `.dockerignore`)
- ✅ Optional - app works with environment variables only

## Security Checklist

- ✅ No `.env` files in Git
- ✅ No credentials in Docker images
- ✅ All secrets in Railway environment variables
- ✅ `.dockerignore` excludes all credential files
- ✅ Application reads only from environment variables

## Troubleshooting

### Backend won't start
- Check that all required environment variables are set in Railway
- Verify `DATABASE_URL` is correct
- Check Railway logs for specific errors

### Admin Panel can't connect to backend
- Verify `NEXT_PUBLIC_BACKEND_URL` is set correctly
- Check CORS settings - ensure admin panel URL is in `CORS_ORIGINS`
- Verify backend is deployed and accessible

### CORS errors
- Ensure `CORS_ORIGINS` includes your admin panel URL
- Format: comma-separated list, e.g., `https://admin.railway.app,https://api.railway.app`
- No spaces after commas (or they will be included in the origin)

## Files Modified

- `backend/.dockerignore` - Excludes credentials
- `admin-panel/.dockerignore` - New file, excludes credentials
- `backend/app/core/config.py` - Optional .env, CORS parsing
- `backend/Dockerfile` - Uses PORT env var
- `admin-panel/Dockerfile` - Uses PORT env var
- `docker-compose.local.yml` - Updated comments
- `docker-compose.yml` - New file for production
- `admin-panel/next.config.js` - NEXT_PUBLIC_ prefix
- `railway.json` - Added deployment notes
- `RAILWAY_ENV_VARS.md` - New file, environment variables reference
- `DEPLOYMENT.md` - This file




