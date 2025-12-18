# Frontend Troubleshooting - Railway

## Problem: Logi pokazują uvicorn (backend) zamiast Node.js (frontend)

Jeśli widzisz w logach:
```
INFO: ... uvicorn ... "GET / HTTP/1.1" 404 Not Found
```

To znaczy, że **otwierasz backend URL zamiast frontend URL**.

## Rozwiązanie

### 1. Sprawdź czy masz 2 serwisy w Railway

W Railway Dashboard powinieneś widzieć **2 serwisy**:
- **Backend** (z `backend/Dockerfile`)
- **Frontend** (z `admin-panel/Dockerfile`)

### 2. Sprawdź URL każdego serwisu

1. Kliknij na **Backend service** → **Settings** → **Networking**
   - Backend URL: `https://ragbotvladislav-production.up.railway.app`
   - To jest API (zwraca JSON, nie HTML)

2. Kliknij na **Frontend service** → **Settings** → **Networking**
   - Frontend URL: `https://admin-panel-production.up.railway.app` (lub podobny)
   - To jest frontend (powinien wyświetlać stronę HTML)

### 3. Użyj Frontend URL

**NIE używaj backend URL do frontendu!**

- ❌ `https://ragbotvladislav-production.up.railway.app` → Backend API
- ✅ `https://admin-panel-production.up.railway.app` → Frontend

### 4. Sprawdź logi Frontend Service

1. W Railway Dashboard, kliknij na **Frontend service**
2. Przejdź do **Logs**
3. Powinieneś widzieć:
   - Node.js logi (nie uvicorn!)
   - Next.js server starting
   - Port information

Jeśli widzisz uvicorn, to znaczy że:
- Otwierasz backend service zamiast frontend service
- Albo frontend service nie jest poprawnie skonfigurowany

### 5. Sprawdź konfigurację Frontend Service

W Railway Dashboard → Frontend Service → Settings:

**Build:**
- Dockerfile Path: `admin-panel/Dockerfile` ✅
- Root Directory: puste (root projektu) ✅

**Deploy:**
- Custom Start Command: **NIE ustawiaj** - Dockerfile ma już CMD ✅
- Healthcheck Path: `/api/health` ✅

**Variables:**
- `NEXT_PUBLIC_BACKEND_URL` = Backend URL ✅

### 6. Sprawdź czy build się powiódł

1. Frontend Service → **Deployments**
2. Sprawdź ostatni deployment
3. Czy build się powiódł?
4. Czy są błędy?

### 7. Sprawdź czy server.js istnieje

W build logach frontend service, sprawdź czy:
- `npm run build` się powiódł
- `.next/standalone` został utworzony
- `server.js` jest w output

## Szybki Test

1. **Backend URL:** `https://ragbotvladislav-production.up.railway.app/health`
   - Powinien zwrócić: `{"status":"healthy"}`

2. **Frontend URL:** `https://admin-panel-production.up.railway.app`
   - Powinien wyświetlić stronę logowania (HTML)

3. **Frontend Health:** `https://admin-panel-production.up.railway.app/api/health`
   - Powinien zwrócić: `{"status":"healthy"}`

## Jeśli nadal nie działa

1. Sprawdź czy frontend service jest **Active** (zielony status)
2. Sprawdź czy frontend service ma **własny URL** (nie używa backend URL)
3. Sprawdź logi frontend service - powinny pokazywać Node.js, nie uvicorn
4. Upewnij się, że używasz **frontend service URL**, nie backend URL
