# Railway Service Configuration - Monorepo Setup

## Problem
Railway nie zapisuje ustawień Dockerfile Path w Dashboard, więc trzeba ustawić to w `railway.json`.

## Rozwiązanie

### Struktura plików

```
/
├── railway.json              # Backend service config
├── backend/
│   ├── Dockerfile
│   └── ...
└── admin-panel/
    ├── railway.json          # Frontend service config
    └── Dockerfile
```

### Backend Service (root railway.json)

Plik `/railway.json` jest używany dla **backend service**:
- `dockerfilePath: "backend/Dockerfile"`
- `watchPatterns: ["backend/**"]` - Railway będzie rebuildować tylko gdy zmienią się pliki w `backend/`

### Frontend Service (admin-panel/railway.json)

Plik `/admin-panel/railway.json` jest używany dla **frontend service**:
- `dockerfilePath: "admin-panel/Dockerfile"`
- `watchPatterns: ["admin-panel/**"]` - Railway będzie rebuildować tylko gdy zmienią się pliki w `admin-panel/`

## Jak Railway wykrywa konfigurację

1. **Backend Service:**
   - Railway używa root `railway.json` (w root projektu)
   - Automatycznie wykrywa `backend/Dockerfile`

2. **Frontend Service:**
   - Railway wykrywa `admin-panel/railway.json` gdy:
     - Serwis jest dodany jako osobny service w Railway Dashboard
     - Lub gdy używasz `railway-compose.yml` (jeśli Railway to wspiera)

## Konfiguracja w Railway Dashboard

### Backend Service
1. Settings → Build:
   - **Dockerfile Path:** `backend/Dockerfile` (z root railway.json)
   - **Root Directory:** puste (root projektu)

### Frontend Service
1. Settings → Build:
   - **Dockerfile Path:** `admin-panel/Dockerfile` (z admin-panel/railway.json)
   - **Root Directory:** puste (root projektu)

**WAŻNE:** Jeśli Railway nie wykrywa `admin-panel/railway.json` automatycznie:
1. W Railway Dashboard → Frontend Service → Settings → Build
2. Ustaw **Dockerfile Path** ręcznie na `admin-panel/Dockerfile`
3. Railway powinien użyć tego ustawienia i zignorować root `railway.json`

## Weryfikacja

Po deploy, sprawdź build logi:

### Backend Service logi powinny pokazywać:
```
COPY backend/requirements.txt requirements.txt
COPY backend/ . 
# Python build, uvicorn start
```

### Frontend Service logi powinny pokazywać:
```
COPY admin-panel/package*.json ./
COPY admin-panel/ .
# npm ci, npm run build, Node.js start
```

## Jeśli Railway nadal używa niewłaściwego Dockerfile

1. **Sprawdź czy masz 2 osobne serwisy:**
   - Backend service
   - Frontend service (admin-panel)

2. **Sprawdź build logi:**
   - Czy pokazują `COPY backend/...` czy `COPY admin-panel/...`?

3. **Wymuś użycie właściwego Dockerfile:**
   - W Railway Dashboard → Frontend Service → Settings → Build
   - Ustaw **Dockerfile Path** = `admin-panel/Dockerfile`
   - Zapisz i zrebuilduj

4. **Sprawdź czy `admin-panel/railway.json` istnieje:**
   - Powinien być w repo
   - Powinien mieć `dockerfilePath: "admin-panel/Dockerfile"`

## Troubleshooting

### Problem: Frontend service używa backend Dockerfile

**Objawy:**
- Build logi pokazują `COPY backend/...`
- Runtime logi pokazują uvicorn/database errors

**Rozwiązanie:**
1. Sprawdź Railway Dashboard → Frontend Service → Settings → Build
2. Ustaw Dockerfile Path = `admin-panel/Dockerfile`
3. Sprawdź czy `admin-panel/railway.json` istnieje i jest poprawny
4. Zrebuilduj service

### Problem: Railway nie wykrywa admin-panel/railway.json

**Rozwiązanie:**
- Railway może wymagać ręcznego ustawienia Dockerfile Path w Dashboard
- Ustaw `admin-panel/Dockerfile` w Settings → Build → Dockerfile Path
- Railway powinien użyć tego ustawienia dla tego serwisu



