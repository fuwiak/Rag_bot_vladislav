# FORCE Railway to use admin-panel/Dockerfile

## Problem
Railway ciągle używa `backend/Dockerfile` dla frontend service, mimo że `admin-panel/railway.json` istnieje.

## Rozwiązanie - WYMUSZENIE w Railway Dashboard

Railway **IGNORUJE** `admin-panel/railway.json` jeśli Root Directory jest niepoprawnie ustawione.

### KROK PO KROKU - OBOWIĄZKOWE!

1. **Otwórz Railway Dashboard**
   - https://railway.app
   - Wybierz projekt
   - Kliknij na **Frontend Service** (admin-panel)

2. **Settings → Build**

3. **USTAW DOKŁADNIE TAK:**

   **Root Directory:** 
   - Zostaw **CAŁKOWICIE PUSTE** (nie wpisuj nic!)
   - **NIE** `admin-panel`
   - **NIE** `/admin-panel`
   - **TAK:** PUSTE pole ✅

   **Dockerfile Path:**
   - Wpisz dokładnie: `admin-panel/Dockerfile` ✅
   - **NIE** `backend/Dockerfile`
   - **NIE** `Dockerfile`
   - **NIE** `/admin-panel/Dockerfile`
   - **TAK:** `admin-panel/Dockerfile` (bez ukośnika na początku!)

4. **Zapisz** (Save)

5. **Zrebuilduj service:**
   - Kliknij "Redeploy" lub "Deploy"
   - Albo Settings → Deployments → "Redeploy"

## Weryfikacja

Po rebuildzie, sprawdź **build logi** frontend service:

✅ **POWINNO pokazywać:**
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
   - Backend service (z backend/Dockerfile)
   - Frontend service (z admin-panel/Dockerfile)

2. **Usuń cache:**
   - Settings → Advanced → Clear Build Cache
   - Zrebuilduj

3. **Sprawdź czy `admin-panel/Dockerfile` istnieje w repo:**
   - Powinien być w katalogu `admin-panel/`
   - Nazwa: `Dockerfile` (z dużą literą D)

4. **Sprawdź czy nie używasz root `railway.json` dla frontend:**
   - Frontend service NIE powinien używać root `railway.json`
   - Root `railway.json` jest TYLKO dla backend service

## Najważniejsze

**W Railway Dashboard → Frontend Service → Settings → Build:**

✅ **Root Directory:** PUSTE (nic nie wpisuj!)  
✅ **Dockerfile Path:** `admin-panel/Dockerfile` (bez ukośnika na początku!)  
❌ **NIE:** `backend/Dockerfile`  
❌ **NIE:** `Dockerfile`  
❌ **NIE:** Root Directory = `admin-panel`

**Po ustawieniu, ZAPISZ i ZREBUILDUJ service!**



