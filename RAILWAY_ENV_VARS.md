# Railway Environment Variables

This document lists all environment variables that must be configured in Railway for deployment.

## Backend Service

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/dbname` |
| `QDRANT_URL` | Qdrant vector database URL | `https://xxx.us-east4-0.gcp.cloud.qdrant.io` |
| `QDRANT_API_KEY` | Qdrant API key | `your_qdrant_api_key` |
| `OPENROUTER_API_KEY` | OpenRouter API key for LLM | `your_openrouter_api_key` |
| `ADMIN_SECRET_KEY` | Secret key for admin authentication | `generate-strong-random-key` |
| `ADMIN_SESSION_SECRET` | Secret for session management | `generate-strong-random-key` |
| `APP_URL` | Public URL of admin panel | `https://your-admin-panel.railway.app` |
| `BACKEND_URL` | Public URL of backend API | `https://your-backend.railway.app` |
| `CORS_ORIGINS` | Comma-separated allowed origins | `https://your-admin-panel.railway.app,https://your-backend.railway.app` |

### Optional Variables (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_MODEL_PRIMARY` | `x-ai/grok-4.1-fast` | Primary LLM model |
| `OPENROUTER_MODEL_FALLBACK` | `openai/gpt-oss-120b:free` | Fallback LLM model |
| `OPENROUTER_TIMEOUT_PRIMARY` | `30` | Primary model timeout (seconds) |
| `OPENROUTER_TIMEOUT_FALLBACK` | `60` | Fallback model timeout (seconds) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model name |
| `EMBEDDING_DIMENSION` | `1536` | Embedding dimension |
| `PORT` | `8000` | Server port (Railway sets this automatically) |

## Admin Panel Service

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_BACKEND_URL` | Backend API URL (accessible in browser) | `https://your-backend.railway.app` |
| `PORT` | Server port | `3000` (Railway may set this automatically) |

## Setting Variables in Railway

1. Go to your Railway project dashboard
2. Select the service (backend or admin-panel)
3. Go to the "Variables" tab
4. Add each variable with its value
5. Click "Deploy" to apply changes

## Security Notes

- **Never commit `.env` files to Git** - they are already in `.gitignore`
- **All credentials must be in Railway environment variables** - not in code or Docker images
- **Use strong, random values** for `ADMIN_SECRET_KEY` and `ADMIN_SESSION_SECRET`
- **Rotate secrets regularly** for production deployments

## Generating Secure Secrets

You can generate secure random secrets using:

```bash
# For ADMIN_SECRET_KEY and ADMIN_SESSION_SECRET
openssl rand -hex 32

# Or using Python
python -c "import secrets; print(secrets.token_hex(32))"
```

## Database URL

**IMPORTANT: You must add a PostgreSQL service to your Railway project!**

1. In your Railway project dashboard, click "+ New" → "Database" → "Add PostgreSQL"
2. Railway will automatically create a PostgreSQL service and provide `DATABASE_URL` as an environment variable
3. The backend service will automatically use this `DATABASE_URL`
4. If you're using an external database, you can set `DATABASE_URL` manually in the backend service's environment variables

**Note:** The application will wait up to 60 seconds for the database to be ready on startup.

## Local Development

For local development, you can still use `.env` files (they are optional):
- Create `.env` in the project root
- Add the same variables as above
- The application will load them for local development only
- `.env` files are excluded from Docker builds and Git




