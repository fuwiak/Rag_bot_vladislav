# Railway Ports Configuration

## Porty w projekcie

### Backend Service (FastAPI)
- **Port:** Railway ustawia automatycznie (zwykle 8000 lub dynamiczny)
- **Dockerfile:** `EXPOSE 8000` (fallback, Railway nadpisuje przez `PORT` env var)
- **Aplikacja:** Uvicorn nasłuchuje na `PORT` environment variable (domyślnie 8000)

### Frontend Service (Next.js)
- **Port:** Railway ustawia automatycznie (zwykle 3000 lub dynamiczny)
- **Dockerfile:** `EXPOSE 3000` (fallback, Railway nadpisuje przez `PORT` env var)
- **Aplikacja:** Next.js standalone automatycznie czyta `PORT` z environment variable

### Telegram Bot
- **Port:** NIE używa własnego portu
- Telegram bot działa przez **polling** (nie webhook)
- Bot komunikuje się z Telegram API przez HTTPS, nie potrzebuje własnego portu

## Jak Railway ustawia porty

Railway automatycznie:
1. Ustawia `PORT` environment variable dla każdego serwisu
2. Port może być 3000, 8080, lub inny dynamiczny port
3. Aplikacja powinna czytać `process.env.PORT` (Node.js) lub `os.environ.get('PORT')` (Python)

## Next.js Standalone i PORT

Next.js standalone server automatycznie:
- Czyta `process.env.PORT` z environment
- Jeśli `PORT` nie jest ustawione, używa domyślnego portu (zwykle 3000)
- **Nie trzeba** ustawiać portu w kodzie - Next.js to robi automatycznie

## Weryfikacja portów

### Backend Service
```bash
# Railway Dashboard → Backend Service → Settings → Networking
# Port: pokazuje aktualny port (np. 8000)
# URL: https://ragbotvladislav-production.up.railway.app
```

### Frontend Service
```bash
# Railway Dashboard → Frontend Service → Settings → Networking
# Port: pokazuje aktualny port (np. 3000)
# URL: https://ragbotvladislav-production-32bf.up.railway.app
```

## Jeśli port jest niepoprawny

1. **Railway automatycznie ustawia PORT** - nie trzeba go konfigurować ręcznie
2. **Sprawdź logi** - powinny pokazywać na jakim porcie aplikacja nasłuchuje:
   - Backend: `INFO: Uvicorn running on http://0.0.0.0:XXXX`
   - Frontend: Next.js logi pokazują port

3. **Jeśli port jest 3000 dla frontend** - to jest **POPRAWNE** dla Next.js
4. **Jeśli port jest 8080** - Railway może ustawić inny port, ale Next.js go odczyta automatycznie

## Podsumowanie

✅ **Frontend (Next.js):** Port 3000 jest **POPRAWNY** - Railway ustawia go automatycznie  
✅ **Backend (FastAPI):** Port 8000 (lub inny ustawiony przez Railway)  
✅ **Telegram Bot:** NIE używa własnego portu - działa przez polling  

**Nie trzeba nic zmieniać** - Railway i aplikacje automatycznie obsługują porty!






