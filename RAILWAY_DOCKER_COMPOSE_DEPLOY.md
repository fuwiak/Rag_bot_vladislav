# Szybki Deploy na Railway przez Docker Compose

## Metoda 1: Railway Docker Compose (ZALECANE)

Railway może używać `railway-compose.yml` do deploy wielu serwisów jednocześnie.

### Krok 1: Przygotuj plik railway-compose.yml

Plik `railway-compose.yml` jest już gotowy w root projektu. Zawiera:
- **Backend service** - FastAPI na porcie 8000
- **Admin Panel service** - Next.js na porcie 3000

### Krok 2: Deploy na Railway

1. **Otwórz Railway Dashboard**
   - https://railway.app
   - Zaloguj się

2. **Utwórz nowy projekt**
   - Kliknij "New Project"
   - Wybierz "Deploy from GitHub repo"
   - Wybierz swój repo: `Rag_bot_vladislav`

3. **Railway automatycznie wykryje docker-compose**
   - Railway szuka `railway-compose.yml` lub `docker-compose.yml` w root
   - Jeśli znajdzie, utworzy wszystkie serwisy automatycznie

4. **Jeśli Railway nie wykryje automatycznie:**
   - Kliknij "New" → "Empty Service"
   - W Settings → Source → wybierz "Docker Compose"
   - Railway użyje `railway-compose.yml` z repo

### Krok 3: Ustaw zmienne środowiskowe

W Railway Dashboard → Project → Variables, dodaj wszystkie wymagane zmienne:

**Backend:**
```
DATABASE_URL=<Railway PostgreSQL URL>
QDRANT_URL=<your_qdrant_url>
QDRANT_API_KEY=<your_key>
OPENROUTER_API_KEY=<your_key>
ADMIN_SECRET_KEY=<random_string>
ADMIN_SESSION_SECRET=<random_string>
BACKEND_URL=<backend_service_url>
CORS_ORIGINS=<backend_url>,<frontend_url>
```

**Frontend:**
```
NEXT_PUBLIC_BACKEND_URL=<backend_service_url>
```

### Krok 4: Dodaj PostgreSQL (jeśli potrzebne)

1. W Railway Dashboard → Project
2. Kliknij "New" → "Database" → "PostgreSQL"
3. Railway automatycznie ustawi `DATABASE_URL` dla wszystkich serwisów

### Krok 5: Deploy

Railway automatycznie zbuduje i wdroży oba serwisy:
- Backend będzie dostępny pod własnym URL
- Frontend będzie dostępny pod własnym URL

---

## Metoda 2: Osobne serwisy (Alternatywa)

Jeśli Railway nie obsługuje docker-compose dla Twojego projektu:

### Krok 1: Utwórz Backend Service

1. Railway Dashboard → New → GitHub Repo
2. Wybierz repo
3. Settings → Build:
   - Dockerfile Path: `backend/Dockerfile`
   - Root Directory: puste
4. Ustaw zmienne środowiskowe (jak wyżej)

### Krok 2: Utwórz Frontend Service

1. Railway Dashboard → New → GitHub Repo
2. Wybierz **to samo** repo
3. Settings → Build:
   - Dockerfile Path: `admin-panel/Dockerfile`
   - Root Directory: puste
4. Ustaw zmienne środowiskowe:
   - `NEXT_PUBLIC_BACKEND_URL` = Backend service URL

### Krok 3: Deploy

Oba serwisy będą działać niezależnie.

---

## Weryfikacja

Po deploy:

1. **Backend:**
   - URL: `https://your-backend-service.up.railway.app`
   - Health: `https://your-backend-service.up.railway.app/health`
   - API Docs: `https://your-backend-service.up.railway.app/docs`

2. **Frontend:**
   - URL: `https://your-frontend-service.up.railway.app`
   - Health: `https://your-frontend-service.up.railway.app/api/health`

3. **Sprawdź logi:**
   - Railway Dashboard → każdy service → Logs
   - Powinny pokazywać poprawne build i start

---

## Troubleshooting

### Problem: Railway nie wykrywa docker-compose

**Rozwiązanie:**
- Upewnij się, że `railway-compose.yml` jest w root projektu
- Lub użyj Metody 2 (osobne serwisy)

### Problem: Serwisy nie widzą się nawzajem

**Rozwiązanie:**
- Użyj Railway service URLs w zmiennych środowiskowych
- Backend URL: Settings → Networking → Public URL
- Frontend URL: Settings → Networking → Public URL

### Problem: Build context errors

**Rozwiązanie:**
- `railway-compose.yml` używa `context: .` (root)
- Dockerfile używa `COPY backend/...` i `COPY admin-panel/...`
- To jest poprawne dla monorepo

---

## Szybki Start - Podsumowanie

1. ✅ `railway-compose.yml` jest gotowy
2. ✅ Railway Dashboard → New Project → GitHub Repo
3. ✅ Railway wykryje docker-compose automatycznie
4. ✅ Ustaw zmienne środowiskowe
5. ✅ Dodaj PostgreSQL (opcjonalnie)
6. ✅ Deploy!

**Gotowe!** Oba serwisy będą działać jednocześnie.





