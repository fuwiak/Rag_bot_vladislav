# Railway Monorepo Setup - Config-as-Code

## ✅ Monorepo działa! Nie potrzebujesz oddzielnych repo

Railway obsługuje monorepo z wieloma serwisami. Kluczowe jest poprawne ustawienie **Root Directory** dla każdego serwisu.

## Struktura projektu

```
/
├── railway.json              # Backend service config (root)
├── backend/
│   ├── Dockerfile
│   └── ...
└── admin-panel/
    ├── railway.json          # Frontend service config
    └── Dockerfile
```

## Konfiguracja w Railway Dashboard

### Backend Service

1. W Railway Dashboard → **Backend Service** → **Settings** → **Build**
2. **Root Directory:** Zostaw **PUSTE** (root projektu) ✅
3. Railway automatycznie użyje root `railway.json`:
   - `dockerfilePath: "backend/Dockerfile"`
   - `watchPatterns: ["backend/**"]`

### Frontend Service

1. W Railway Dashboard → **Frontend Service** → **Settings** → **Build**
2. **Root Directory:** Zostaw **PUSTE** (root projektu) ✅
   - **WAŻNE:** Railway wykryje `admin-panel/railway.json` automatycznie
   - Jeśli nie wykrywa, ustaw ręcznie: **Dockerfile Path** = `admin-panel/Dockerfile`

## Pliki Config-as-Code

### `/railway.json` (Backend)

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "backend/Dockerfile",
    "watchPatterns": ["backend/**"]
  },
  "deploy": {
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### `/admin-panel/railway.json` (Frontend)

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "admin-panel/Dockerfile",
    "watchPatterns": ["admin-panel/**"]
  },
  "deploy": {
    "healthcheckPath": "/api/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

## Jak Railway wykrywa konfigurację

1. **Backend Service:**
   - Railway używa root `railway.json` (w root projektu)
   - Automatycznie wykrywa `dockerfilePath: "backend/Dockerfile"`

2. **Frontend Service:**
   - Railway **powinien** automatycznie wykryć `admin-panel/railway.json`
   - Jeśli nie wykrywa, ustaw ręcznie w Dashboard:
     - **Dockerfile Path:** `admin-panel/Dockerfile`
     - **Root Directory:** puste

## Watch Patterns

- **Backend:** Rebuilduje tylko gdy zmienią się pliki w `backend/**`
- **Frontend:** Rebuilduje tylko gdy zmienią się pliki w `admin-panel/**`

To zapobiega niepotrzebnym rebuildom - zmiana w backend nie triggeruje rebuild frontend i vice versa.

## Troubleshooting

### Problem: Frontend service używa backend Dockerfile

**Objawy:**
- Build logi pokazują `COPY backend/...`
- Runtime logi pokazują uvicorn/database errors

**Rozwiązanie:**
1. Railway Dashboard → Frontend Service → Settings → Build
2. Ustaw **Dockerfile Path** = `admin-panel/Dockerfile`
3. Upewnij się, że **Root Directory** jest puste
4. Sprawdź czy `admin-panel/railway.json` istnieje w repo
5. Zrebuilduj service

### Problem: Railway nie wykrywa admin-panel/railway.json

**Rozwiązanie:**
- Railway może wymagać ręcznego ustawienia Dockerfile Path w Dashboard
- Ustaw `admin-panel/Dockerfile` w Settings → Build → Dockerfile Path
- Railway powinien użyć tego ustawienia i zignorować root `railway.json` dla tego serwisu

### Problem: Zmiany w backend triggerują rebuild frontend

**Rozwiązanie:**
- Sprawdź czy `admin-panel/railway.json` ma `watchPatterns: ["admin-panel/**"]`
- Sprawdź czy backend service ma `watchPatterns: ["backend/**"]`
- Railway powinien używać tych wzorców do decydowania, który service rebuildować

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

## Podsumowanie

✅ **Monorepo działa** - nie potrzebujesz oddzielnych repo  
✅ **Config-as-Code** - każdy service ma swój `railway.json`  
✅ **Watch Patterns** - zapobiegają niepotrzebnym rebuildom  
✅ **Root Directory** - puste dla obu serwisów (Railway używa root jako build context)









