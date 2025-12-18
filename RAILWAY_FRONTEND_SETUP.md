# How to Deploy Frontend (Admin Panel) on Railway

Frontend musi być deployowany jako **osobny serwis** w Railway. Obecnie masz tylko backend, dlatego frontend zwraca 404.

## Opcja 1: Dodaj Frontend jako Osobny Serwis (Zalecane)

### Krok 1: Dodaj Nowy Serwis w Railway

1. W Railway Dashboard, w Twoim projekcie, kliknij **"+ New"**
2. Wybierz **"GitHub Repo"** (jeśli jeszcze nie masz połączonego repo) lub **"Empty Service"**
3. Jeśli używasz tego samego repo:
   - Wybierz istniejące repo
   - Railway zapyta o typ serwisu
   - Wybierz **"Dockerfile"** lub **"Nixpacks"**

### Krok 2: Skonfiguruj Frontend Service

1. W ustawieniach nowego serwisu:
   - **Root Directory:** Zostaw puste (root projektu)
   - **Dockerfile Path:** `admin-panel/Dockerfile`
   - Railway automatycznie użyje root jako build context

2. Railway automatycznie wykryje `admin-panel/railway.json` jeśli istnieje

**WAŻNE:** Dockerfile jest już skonfigurowany do pracy z root context (kopiuje `admin-panel/` zamiast `.`)

### Krok 3: Ustaw Zmienne Środowiskowe

W frontend service, dodaj w **Variables**:
- `NEXT_PUBLIC_BACKEND_URL` = URL Twojego backend service (np. `https://ragbotvladislav-production.up.railway.app`)
- `PORT` = Railway ustawi automatycznie (zwykle 8080)

### Krok 4: Deploy

Railway automatycznie zbuduje i wdroży frontend. Po deploy:
- Frontend będzie dostępny pod własnym URL (np. `https://admin-panel-production.up.railway.app`)
- Backend pozostanie pod swoim URL

## Opcja 2: Użyj Docker Compose (Alternatywa)

Railway wspiera docker-compose, ale wymaga to konfiguracji:

1. W Railway Dashboard:
   - Utwórz nowy serwis
   - Wybierz **"Docker Compose"** jako builder
   - Railway użyje `railway-compose.yml` z root projektu

2. Ustaw wszystkie zmienne środowiskowe w Railway (dla obu serwisów)

**Uwaga:** Docker Compose w Railway może być bardziej skomplikowane do zarządzania.

## Sprawdzenie

Po deploy frontendu:

1. **Backend URL:** `https://ragbotvladislav-production.up.railway.app`
   - Powinien zwracać JSON API
   - Health check: `https://ragbotvladislav-production.up.railway.app/health`

2. **Frontend URL:** `https://admin-panel-production.up.railway.app` (lub podobny)
   - Powinien wyświetlać stronę logowania
   - Health check: `https://admin-panel-production.up.railway.app/api/health`

## Troubleshooting

### Frontend zwraca 404

- Sprawdź czy frontend service jest uruchomiony w Railway
- Sprawdź logi frontend service w Railway
- Upewnij się, że `admin-panel/Dockerfile` jest poprawny
- Sprawdź czy `server.js` jest w build output

### Frontend nie może połączyć się z backendem

- Sprawdź `NEXT_PUBLIC_BACKEND_URL` - musi być pełny URL backend service
- Sprawdź CORS w backend - `CORS_ORIGINS` musi zawierać URL frontendu
- Sprawdź czy backend jest dostępny publicznie

### Port conflicts

- Railway automatycznie przypisuje porty
- Frontend i backend będą miały różne porty
- Railway automatycznie tworzy publiczne URL dla każdego serwisu

## Zalecana Konfiguracja

**Backend Service:**
- Dockerfile: `backend/Dockerfile`
- Port: Automatyczny (Railway)
- Health: `/health`

**Frontend Service:**
- Dockerfile: `admin-panel/Dockerfile`  
- Port: Automatyczny (Railway)
- Health: `/api/health`
- Environment: `NEXT_PUBLIC_BACKEND_URL` = Backend URL

**Zmienne Środowiskowe (oba serwisy):**
- Backend: Wszystkie zmienne z `RAILWAY_ENV_VARS.md`
- Frontend: Tylko `NEXT_PUBLIC_BACKEND_URL`


