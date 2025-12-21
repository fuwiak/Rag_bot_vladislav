# FIX: Railway Frontend Service - Dockerfile Path

## Problem
Railway ciągle używa `backend/Dockerfile` dla frontend service zamiast `admin-panel/Dockerfile`.

## ✅ Rozwiązanie - KROK PO KROKU (OBOWIĄZKOWE!)

### Konfiguracja w Railway Dashboard

**WAŻNE:** Railway może ignorować `admin-panel/railway.json`, więc musisz ustawić to **ręcznie w Dashboard**.

1. **Otwórz Railway Dashboard**
   - https://railway.app
   - Wybierz swój projekt
   - Kliknij na **Frontend Service** (admin-panel)

2. **Przejdź do Settings → Build**

3. **USTAW TAK:**
   - **Root Directory:** Zostaw **PUSTE** (root projektu) ✅
     - **NIE** ustawiaj `admin-panel` tutaj!
     - Build context musi być root, bo Dockerfile używa `COPY admin-panel/...`
   
   - **Dockerfile Path:** Ustaw na `admin-panel/Dockerfile` ✅
     - **NIE** `backend/Dockerfile`!
     - **NIE** `Dockerfile`!
     - **TAK:** `admin-panel/Dockerfile` (pełna ścieżka od root)

4. **Zapisz zmiany** (Save)

5. **Zrebuilduj service:**
   - Kliknij "Redeploy" lub "Deploy" w najnowszym deployment

### Dlaczego Root Directory = puste?

Dockerfile używa:
```dockerfile
COPY admin-panel/package*.json ./
COPY admin-panel/ .
```

To oznacza, że **build context musi być root projektu**, nie `admin-panel/`. Dlatego:
- ✅ Root Directory = **puste** (root)
- ✅ Dockerfile Path = `admin-panel/Dockerfile` (pełna ścieżka)

## Weryfikacja

Po ustawieniu, sprawdź build logi frontend service:

✅ **Powinno pokazywać:**
```
COPY admin-panel/package*.json ./
COPY admin-panel/ .
npm ci
npm run build
```

❌ **NIE powinno pokazywać:**
```
COPY backend/requirements.txt
uvicorn
database connection
```

## Jeśli nadal nie działa

1. **Sprawdź czy masz 2 osobne serwisy:**
   - Backend service
   - Frontend service (admin-panel)

2. **Sprawdź czy frontend service używa `admin-panel/railway.json`:**
   - Railway może ignorować `admin-panel/railway.json` jeśli Root Directory jest ustawione
   - W takim przypadku ustaw Dockerfile Path ręcznie w Dashboard

3. **Usuń cache Railway:**
   - Settings → Advanced → Clear Build Cache
   - Zrebuilduj service

4. **Sprawdź czy `admin-panel/Dockerfile` istnieje w repo:**
   - Powinien być w katalogu `admin-panel/`
   - Nazwa: `Dockerfile` (z dużą literą D)

## Konfiguracja w plikach (już ustawiona)

### `admin-panel/railway.json` (już poprawnie skonfigurowany)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "admin-panel/Dockerfile",  // ✅ Poprawnie
    "watchPatterns": ["admin-panel/**"]
  }
}
```

### `railway.json` (root - dla backend)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "backend/Dockerfile",  // ✅ Backend
    "watchPatterns": ["backend/**"]
  }
}
```

## ⚠️ WAŻNE - Railway może ignorować railway.json!

Railway **może nie wykryć automatycznie** `admin-panel/railway.json` dla frontend service. 

**Dlatego MUSISZ ustawić ręcznie w Dashboard:**

1. Frontend Service → Settings → Build
2. **Root Directory:** PUSTE ✅
3. **Dockerfile Path:** `admin-panel/Dockerfile` ✅
4. Zapisz i zrebuilduj

## Najważniejsze - PODSUMOWANIE

**W Railway Dashboard → Frontend Service → Settings → Build:**

✅ **Root Directory:** PUSTE (root projektu)  
✅ **Dockerfile Path:** `admin-panel/Dockerfile`  
❌ **NIE:** `backend/Dockerfile`  
❌ **NIE:** `Dockerfile`  
❌ **NIE:** Root Directory = `admin-panel`

**Po ustawieniu, zrebuilduj service i sprawdź logi!**



