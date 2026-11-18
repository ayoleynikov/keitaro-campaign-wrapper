# Запуск (mock)

## Требования

- Python 3.12+, Node 22+ (для dev-фронта)
- `pip install -r backend/requirements.txt`, `npm ci` в `frontend/`

## Локально (без Docker)

```bash
cp .env.example .env   # KEITARO_MODE=mock, без секретов

cd backend
PYTHONPATH=. python3 -m alembic upgrade head
PYTHONPATH=. python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8801

# другой терминал
cd frontend
npm ci
npm run dev
```

- UI: http://127.0.0.1:43123
- API: http://127.0.0.1:8801/api/health — `keitaro_mode` должен быть `mock`

БД по умолчанию: `backend/data/app.db` (путь не зависит от cwd). См. SQLite recovery в [README.md](../README.md).

### Команды проверки

```bash
cd backend && PYTHONPATH=. python3 -m pytest -q          # 46 passed на момент публикации
cd frontend && npm run build
python3 scripts/ui_smoke_playwright.py                    # нужен dev-сервер 43123; опционально
```

## Docker Compose (mock)

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

- Migrations: в entrypoint бэкенда (`alembic upgrade head`).
- Том `backend-data` → `/app/data` (отдельно от `backend/data` на хосте при dev).
- Прокси фронта: `VITE_DEV_API_PROXY=http://backend:8801` (уже в `docker-compose.yml`).

На машине подготовки этого снимка Docker-демон отсутствовал. Более ранний прогон compose в другом окружении был **до** поздних изменений backend и здесь не повторялся.

## Live

Не включайте `KEITARO_MODE=live` без явного решения. Guard'ы и ограничения: [SAFETY.md](SAFETY.md), факты live QA: [LIVE_QA.md](LIVE_QA.md). Имена фильтров/экшенов в mock (`country`, `http`) на live наблюдались при создании test-кампании; полный каталог офферов ключа для multi-offer Push **не** был достаточным (один видимый оффер).
