# How to Add PostgreSQL to Railway Project

This guide will walk you through adding PostgreSQL database to your Railway project.

## Step-by-Step Instructions

### Step 1: Open Your Railway Project

1. Go to [Railway Dashboard](https://railway.app)
2. Select your project (or create a new one)
3. You should see your backend service in the project

### Step 2: Add PostgreSQL Service

1. In your Railway project dashboard, click the **"+ New"** button (usually in the top right or bottom of the services list)
2. From the dropdown menu, select **"Database"**
3. Select **"Add PostgreSQL"**
4. Railway will automatically:
   - Create a new PostgreSQL service
   - Generate a secure database
   - Create `DATABASE_URL` environment variable
   - Make it available to all services in the project

### Step 3: Verify DATABASE_URL is Available

1. Click on your **backend service** in Railway
2. Go to the **"Variables"** tab
3. You should see `DATABASE_URL` automatically listed (it's shared from the PostgreSQL service)
4. The `DATABASE_URL` may be in one of two formats:
   - **Resolved format:** `postgresql://postgres:password@hostname:5432/railway` (Railway automatically resolves variables)
   - **Template format:** `postgresql://${{PGUSER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:5432/${{PGDATABASE}}` (Railway template with variables)

**Note:** 
- Railway usually resolves the template automatically, but if you see the template format, the application will automatically resolve it using environment variables
- You don't need to manually copy or set `DATABASE_URL` - Railway does this automatically!
- The application supports both formats and will resolve variables if needed

### Step 4: Deploy Your Backend

1. Railway will automatically redeploy your backend service when you add the PostgreSQL service
2. Or you can manually trigger a deployment:
   - Go to your backend service
   - Click **"Deploy"** or **"Redeploy"**

### Step 5: Verify Connection

1. Check the deployment logs in Railway
2. You should see:
   ```
   INFO - Using database URL: postgresql://postgres:****@...
   INFO - Waiting for database to be ready...
   INFO - Database connection successful
   INFO - Database tables initialized successfully
   ```

## How It Works

### Automatic Integration

When you add PostgreSQL service to your Railway project:

1. **Railway creates the database** - A new PostgreSQL instance is created
2. **DATABASE_URL is generated** - Railway creates a connection string automatically
3. **Environment variable is shared** - `DATABASE_URL` is automatically available to all services in the project
4. **Backend connects automatically** - Your backend service reads `DATABASE_URL` from environment variables and connects

### Application Behavior

Your application is already configured to:
- ✅ Read `DATABASE_URL` from environment variables
- ✅ Wait up to 60 seconds for database to be ready
- ✅ Automatically create database tables on startup
- ✅ Retry connection if database is not immediately available
- ✅ Use connection pooling for better performance

## Troubleshooting

### Database connection still fails

1. **Check if PostgreSQL service is running:**
   - Go to PostgreSQL service in Railway
   - Check if it shows "Active" status
   - If not, wait a few minutes for it to start

2. **Verify DATABASE_URL is set:**
   - Go to backend service → Variables tab
   - Look for `DATABASE_URL` in the list
   - If missing, the PostgreSQL service might not be in the same project

3. **Check deployment logs:**
   - Look for error messages about database connection
   - The application will retry 30 times (60 seconds total)
   - If it still fails, check the error message for details

### DATABASE_URL not showing in backend service

1. Make sure PostgreSQL service is in the **same Railway project** as your backend
2. Try redeploying the backend service after adding PostgreSQL
3. Check that PostgreSQL service is active and running

### Database tables not created

1. Check deployment logs for migration errors
2. The application runs `alembic upgrade head` on startup
3. If migrations fail, check the error message in logs
4. Tables are also created automatically via SQLAlchemy if migrations fail

## Manual Database URL (External Database)

If you're using an external PostgreSQL database (not Railway's):

1. Go to backend service → Variables tab
2. Click **"+ New Variable"**
3. Name: `DATABASE_URL`
4. Value: Your PostgreSQL connection string
   - Format: `postgresql://username:password@host:port/database`
   - Example: `postgresql://user:pass@db.example.com:5432/mydb`
5. Click **"Add"**
6. Redeploy your backend service

## Next Steps

After PostgreSQL is set up:

1. ✅ Database is ready
2. ✅ Backend can connect
3. ✅ Tables are created automatically
4. ✅ Application is ready to use

You can now:
- Access your API endpoints
- Create projects and users
- Upload documents
- Use the admin panel

## Additional Resources

- [Railway PostgreSQL Documentation](https://docs.railway.app/databases/postgresql)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)
- See `RAILWAY_ENV_VARS.md` for all required environment variables






