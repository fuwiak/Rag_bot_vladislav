# Szybka Naprawa Frontendu w Railway

## Problem
Backend zwraca `{"detail":"Not Found"}` dla `/` bo to tylko API. Frontend **MUSI** być osobnym serwisem.

## Rozwiązanie - Krok po Kroku

### 1. Otwórz Railway Dashboard
- Idź do https://railway.app
- Wybierz swój projekt

### 2. Dodaj Nowy Serwis dla Frontendu

1. Kliknij **"+ New"** (w prawym górnym rogu lub na dole listy serwisów)
2. Wybierz **"GitHub Repo"**
3. Wybierz to samo repo co backend (Rag_bot_vladislav)
4. Railway automatycznie wykryje, że to nowy serwis

### 3. Skonfiguruj Frontend Service

1. W nowym serwisie, przejdź do **Settings** (⚙️)
2. W sekcji **Build**:
   - **Dockerfile Path:** `admin-panel/Dockerfile`
   - **Root Directory:** Zostaw puste (root projektu)
3. Railway automatycznie użyje root jako build context

### 4. Ustaw Zmienne Środowiskowe

1. W frontend service, przejdź do **Variables**
2. Dodaj:
   - **NEXT_PUBLIC_BACKEND_URL** = `https://ragbotvladislav-production.up.railway.app`
     (Użyj URL Twojego backend service - znajdziesz go w Settings → Networking)

### 5. Deploy

1. Railway automatycznie zbuduje i wdroży frontend
2. Po deploy, frontend będzie dostępny pod własnym URL (np. `https://admin-panel-production.up.railway.app`)
3. Sprawdź logi, czy build się powiódł

### 6. Sprawdź CORS w Backend

Upewnij się, że w backend service → Variables masz:
- **CORS_ORIGINS** = `https://ragbotvladislav-production.up.railway.app,https://admin-panel-production.up.railway.app`
  (Dodaj URL frontendu do CORS_ORIGINS)

## Sprawdzenie

Po deploy:
- **Backend:** `https://ragbotvladislav-production.up.railway.app/health` → `{"status":"healthy"}`
- **Frontend:** `https://admin-panel-production.up.railway.app` → Strona logowania

## Jeśli nadal nie działa

### Sprawdź czy frontend service jest aktywny

1. W Railway Dashboard, sprawdź czy masz **2 serwisy**:
   - Backend service (z backend/Dockerfile)
   - Frontend service (z admin-panel/Dockerfile)

2. **WAŻNE:** Upewnij się, że otwierasz **frontend service URL**, nie backend URL!
   - Backend URL: `https://ragbotvladislav-production.up.railway.app` → To jest API (zwraca JSON)
   - Frontend URL: `https://admin-panel-production.up.railway.app` → To jest frontend (powinien wyświetlać stronę)

3. Sprawdź logi **frontend service** (nie backend!):
   - Powinny pokazywać Node.js, nie uvicorn
   - Jeśli widzisz uvicorn, to otwierasz backend service

4. Sprawdź build logi frontend service:
   - Czy build się powiódł?
   - Czy `server.js` został utworzony?
   - Czy są błędy podczas build?

5. Sprawdź czy frontend service ma ustawione:
   - Dockerfile Path: `admin-panel/Dockerfile`
   - Root Directory: puste (root projektu)

### Debugowanie

Jeśli logi pokazują uvicorn (backend), to znaczy że:
- Otwierasz backend URL zamiast frontend URL
- Albo frontend service nie jest uruchomiony
- Albo Railway używa backend service zamiast frontend service

**Rozwiązanie:** Upewnij się, że masz **2 osobne serwisy** w Railway i używasz **frontend service URL**.
















