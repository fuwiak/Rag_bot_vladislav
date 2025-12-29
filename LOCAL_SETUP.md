# Local Development Setup

## Quick Start - Docker Compose (Recommended)

### 1. Start all services

```bash
docker-compose -f docker-compose.local.yml up
```

This will start:
- **PostgreSQL** on port `5432`
- **Backend API** on port `8000`
- **Admin Panel** on port `3000`

### 2. Initialize database

In a new terminal:

```bash
# Run migrations
docker-compose -f docker-compose.local.yml exec backend alembic upgrade head

# Create admin user
docker-compose -f docker-compose.local.yml exec backend python create_admin.py
```

### 3. Access the application

- **Admin Panel**: http://localhost:3000
  - Default login: `admin` / `admin123`
- **Backend API**: http://localhost:8000
  - API docs: http://localhost:8000/docs
  - Health check: http://localhost:8000/health

### 4. Stop services

```bash
docker-compose -f docker-compose.local.yml down
```

---

## Manual Setup (Without Docker)

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (installed locally)

### 1. Setup PostgreSQL

```bash
# Create database
createdb rag_bot_db

# Or via psql:
psql -U postgres
CREATE DATABASE rag_bot_db;
\q
```

### 2. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/Mac:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or use fast install script (Linux/Mac):
# ./install-fast.sh

# Create .env file (or use root .env)
# DATABASE_URL=postgresql://user:password@localhost:5432/rag_bot_db
# QDRANT_API_KEY=your_key
# OPENROUTER_API_KEY=your_key
# ADMIN_SECRET_KEY=random_string
# ADMIN_SESSION_SECRET=random_string

# Run migrations
alembic upgrade head

# Create admin user
python create_admin.py
```

### 3. Start Backend

```bash
# In backend directory, with venv activated
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or use start script:
./start.sh
```

### 4. Setup Admin Panel

Open a new terminal:

```bash
cd admin-panel

# Install dependencies
npm install

# Create .env.local
echo "NEXT_PUBLIC_BACKEND_URL=http://localhost:8000" > .env.local

# Start dev server
npm run dev
```

### 5. Access the application

- **Admin Panel**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs

---

## Environment Variables

Create a `.env` file in the root directory:

```env
# Database
DATABASE_URL=postgresql://ragbot:ragbot@localhost:5432/rag_bot_db

# Qdrant Vector DB
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your_qdrant_api_key

# OpenRouter LLM
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL_PRIMARY=x-ai/grok-4.1-fast
OPENROUTER_MODEL_FALLBACK=openai/gpt-oss-120b:free

# Admin Panel
ADMIN_SECRET_KEY=your_random_secret_key
ADMIN_SESSION_SECRET=your_random_session_secret

# CORS (for local development)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

---

## Troubleshooting

### Port already in use

If ports 3000, 8000, or 5432 are busy, change them in:
- `docker-compose.local.yml` (for Docker)
- Command line arguments (for manual setup)

### Database connection errors

Make sure:
- PostgreSQL is running
- `DATABASE_URL` is correct in `.env`
- Database exists

### Qdrant or OpenRouter errors

Check that:
- API keys are correctly set in `.env`
- You have access to Qdrant Cloud
- You have access to OpenRouter API

### grpcio installation issues

If `grpcio` installation takes too long:

**Linux/Mac:**
```bash
pip install --only-binary :all: grpcio grpcio-tools
pip install -r requirements.txt
```

**Or use script:**
```bash
./install-fast.sh
```

### Migration issues

```bash
# View current version
alembic current

# Apply all migrations
alembic upgrade head

# Rollback migration (careful!)
alembic downgrade -1
```

---

## Development Tips

1. **Hot reload**: Both backend and frontend support hot reload
   - Backend: `--reload` flag in uvicorn
   - Frontend: Next.js dev server automatically reloads

2. **Database migrations**: Run migrations after pulling changes
   ```bash
   alembic upgrade head
   ```

3. **View logs**: 
   - Docker: `docker-compose -f docker-compose.local.yml logs -f`
   - Manual: Check terminal output

4. **Reset database**:
   ```bash
   # Docker
   docker-compose -f docker-compose.local.yml down -v
   docker-compose -f docker-compose.local.yml up
   
   # Manual
   dropdb rag_bot_db && createdb rag_bot_db
   alembic upgrade head
   ```















