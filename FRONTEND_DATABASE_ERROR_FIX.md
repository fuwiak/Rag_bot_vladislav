# Fix: Frontend Service używa Backend Dockerfile

## Problem

Podczas deploy frontend service widzisz błędy bazy danych:
```
TimeoutError
Migrations failed or already applied
Waiting for database to be ready...
```

To znaczy, że **frontend service używa backend Dockerfile** zamiast `admin-panel/Dockerfile`.

## Przyczyna

Railway może używać root `railway.json` (który wskazuje na `backend/Dockerfile`) dla wszystkich serwisów, jeśli nie ma osobnej konfiguracji.

## Rozwiązanie

### Opcja 1: Ustaw Dockerfile Path w Railway Dashboard (ZALECANE)

1. Otwórz Railway Dashboard
2. Kliknij na **Frontend Service** (admin-panel)
3. Przejdź do **Settings** (⚙️)
4. W sekcji **Build**:
   - **Dockerfile Path:** `admin-panel/Dockerfile` ✅
   - **Root Directory:** Zostaw puste (root projektu) ✅
5. **WAŻNE:** Upewnij się, że **NIE** używasz root `railway.json` dla frontend service
6. Zapisz zmiany
7. Railway automatycznie zrebuilduje service

### Opcja 2: Usuń root railway.json (jeśli masz osobne serwisy)

Jeśli masz 2 osobne serwisy w Railway:
- **Backend Service** → używa `railway.json` z root (lub backend/railway.json)
- **Frontend Service** → używa `admin-panel/railway.json`

Możesz przenieść root `railway.json` do `backend/railway.json` i upewnić się, że Railway używa odpowiednich plików dla każdego serwisu.

### Opcja 3: Sprawdź konfigurację serwisu

W Railway Dashboard → Frontend Service → Settings:

**Build:**
- Builder: `DOCKERFILE` ✅
- Dockerfile Path: `admin-panel/Dockerfile` ✅ (NIE `backend/Dockerfile`!)
- Root Directory: puste ✅

**Deploy:**
- Custom Start Command: **NIE ustawiaj** (Dockerfile ma już CMD) ✅
- Healthcheck Path: `/api/health` ✅

## Weryfikacja

Po poprawieniu konfiguracji:

1. **Build logi frontend service** powinny pokazywać:
   - `npm ci` (instalacja Node.js dependencies)
   - `npm run build` (Next.js build)
   - `COPY admin-panel/...` (nie backend/)

2. **Runtime logi frontend service** powinny pokazywać:
   - Node.js server starting
   - Next.js server on port...
   - **NIE** uvicorn, **NIE** database connection, **NIE** migrations

3. **Backend service** powinien pokazywać:
   - uvicorn
   - database connection
   - migrations

## Jeśli nadal nie działa

1. Sprawdź czy frontend service ma **własny URL** (nie używa backend URL)
2. Sprawdź build logi - czy używa `admin-panel/Dockerfile`?
3. Sprawdź czy `admin-panel/railway.json` istnieje i jest poprawny
4. Upewnij się, że w Railway Dashboard → Frontend Service → Settings → Build → Dockerfile Path = `admin-panel/Dockerfile`











