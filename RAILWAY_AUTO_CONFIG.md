# Railway Auto-Configuration - Bez ręcznych ustawień

## Zmiany w strukturze

1. **Przeniesiono root `railway.json` → `backend/railway.json`**
   - Backend service używa `backend/railway.json`
   - Frontend service używa `admin-panel/railway.json`

2. **Zmieniono `admin-panel/Dockerfile`**
   - Teraz build context jest `admin-panel/` (nie root)
   - `COPY package*.json ./` zamiast `COPY admin-panel/package*.json ./`
   - `COPY . .` zamiast `COPY admin-panel/ .`

3. **Zmieniono `admin-panel/railway.json`**
   - `dockerfilePath: "Dockerfile"` (relatywnie do admin-panel/)
   - Railway automatycznie wykryje Root Directory = `admin-panel`

## Jak Railway wykrywa konfigurację

### Backend Service
- Railway wykrywa `backend/railway.json`
- Automatycznie używa Root Directory = `backend`
- Dockerfile Path = `backend/Dockerfile` (z railway.json)

### Frontend Service
- Railway wykrywa `admin-panel/railway.json`
- Automatycznie używa Root Directory = `admin-panel`
- Dockerfile Path = `Dockerfile` (relatywnie do admin-panel/)

## Weryfikacja

Po deploy, sprawdź build logi:

### Backend Service
```
COPY backend/requirements.txt requirements.txt
COPY backend/ .
# Python build, uvicorn start
```

### Frontend Service
```
COPY package*.json ./
COPY . .
npm ci
npm run build
```

## Jeśli Railway nadal używa backend Dockerfile dla frontend

1. **Sprawdź czy masz 2 osobne serwisy:**
   - Backend service
   - Frontend service (admin-panel)

2. **Sprawdź czy Railway wykrywa `admin-panel/railway.json`:**
   - Railway powinien automatycznie wykryć ten plik
   - Jeśli nie, może wymagać ręcznego ustawienia Root Directory = `admin-panel` w Dashboard

3. **Usuń cache:**
   - Settings → Advanced → Clear Build Cache
   - Zrebuilduj service

## Podsumowanie

✅ **Backend:** `backend/railway.json` → Root Directory = `backend`  
✅ **Frontend:** `admin-panel/railway.json` → Root Directory = `admin-panel`  
✅ **Dockerfile frontend:** Działa z Root Directory = `admin-panel`  
✅ **Automatyczna konfiguracja:** Railway powinien wykryć wszystko automatycznie

**Nie trzeba ręcznie ustawiać w Dashboard!**






