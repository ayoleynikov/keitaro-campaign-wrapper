# Release QA (2026-11-18, обновление sqlite + UI smoke)

Профиль: **mock only**, private draft, без live Keitaro. Docker — только изолированный compose на VM.

## Команды и результаты

| Шаг | Команда | Результат |
|-----|---------|-----------|
| Backend deps | `pip install -r backend/requirements.txt` | OK (ранее) |
| Migrations default path | `cd backend && PYTHONPATH=. python3 -m alembic upgrade head` | 001→003, `backend/data/app.db` |
| Migrations isolated path | `DATABASE_URL=sqlite:////tmp/keitaro-isolated-qa.db PYTHONPATH=. python3 -m alembic upgrade head` | OK, существующий `app.db` не трогался |
| Tests | `cd backend && PYTHONPATH=. python3 -m pytest -q` | **46 passed** на момент подготовки публикации (включая live-guard и payload tests) |
| Frontend | `cd frontend && npm run build` | OK (`tsc -b && vite build`) |
| Backend health | `curl http://127.0.0.1:8801/api/health` | `{"status":"ok","keitaro_mode":"mock"}` |
| API smoke POST | `POST /api/campaigns` на **8801**, `backend/data/app.db` | 200, запись в SQLite |
| Persistence | restart uvicorn → `sqlite3 … "select keitaro_campaign_id from operations"` | строки **2000–2002** сохранены |
| Frontend dev | `curl -o /dev/null -w %{http_code} http://127.0.0.1:43123/` | 200 |
| Docker build/up | `sudo docker compose build && sudo docker compose up -d` | **VERIFIED** (см. ниже) |
| Live Keitaro | ограниченный scope | creator + Fetch + local editor на одном оффере — да; **multi-offer Push — NOT VERIFIED** (см. LIVE_QA.md) |

## Readonly SQLite: причина и исправление

**Симптом:** `attempt to write a readonly database` на штатном `8801` при живом `health`.

**Корневая причина (подтверждено):** процесс uvicorn держал FD на `backend/data/app.db` **(deleted)** — файл был удалён/пересоздан при работающем сервере; новая БД на диске не использовалась.

**Дополнительный риск:** относительный `sqlite:///./data/app.db` и `Path("data")` зависели от **cwd** процесса.

**Исправление в коде:**

- `app/db/sqlite_paths.py` — путь SQLite всегда относительно `backend/`, проверка записи при старте, сообщение **Non-destructive recovery** (без `rm app.db`).
- `config.py` — `.env` из `backend/.env` и корня репозитория.

**Недеструктивное восстановление (документировано):**

1. Остановить все процессы, использующие БД, и запустить uvicorn снова.
2. `chmod u+rwX backend/data` и права на файл, если read-only.
3. Для изолированного прогона: `DATABASE_URL=sqlite:////tmp/your-qa.db` + `alembic upgrade head` (старый `app.db` остаётся).
4. **Не** удалять `app.db` при работающем API.

## Исправления в ходе QA (накопительно)

1. TypeScript build — `import type` для verbatimModuleSyntax.
2. Pytest isolation — отдельная SQLite на тест, `init_db` в `conftest`.
3. Fetch при dirty + `is_new_unpublished`.
4. Mock `fail_update_stream_ids` для push failure.
5. `tests/test_editor_qa.py` — allocation, cancel, fetch dirty.
6. **SQLite startup hardening** — см. выше.
7. **Docker frontend proxy** — `VITE_DEV_API_PROXY=http://backend:8801` в compose.

## Docker QA (2026-11-18, VM)

**Блокер до установки:** `docker: command not found`. Установка: `sudo apt-get install -y docker.io`, ручной `dockerd` (init в образе VM без автозапуска).

| Шаг | Результат |
|-----|-----------|
| `sudo docker compose build` | backend + frontend OK |
| `sudo docker compose up -d` | backend Up; frontend — порт 43123 занят dev → `fuser -k` + повторный `up -d frontend` |
| Migrations | лог: `alembic` 001→003, uvicorn 8801 |
| `curl :8801/api/health` | `mock` |
| `curl :43123/api/health` | прокси → backend OK |
| `POST /api/campaigns` в контейнере | `operation_id` 6, volume DB |
| `docker compose restart backend` | `operations` count **6 → 6** |
| Host `backend/data/app.db` | **не удалялась** (отдельная dev-БД) |

Полный чеклист: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Запуск: [RUN_LOCAL.md](RUN_LOCAL.md).

## Secret hygiene

- `.env.example` — плейсхолдеры; ключ пустой.
- Ключ не на frontend (`/api/health` без секретов).
- Архив исключает `.env`, `backend/data/*.db`, `node_modules`, кэши.

## UI smoke (mock, browser)

Инструмент: **Playwright** (`python3 scripts/ui_smoke_playwright.py`) против dev-сервера `43123` → API `8801`.

| Проверка | Статус |
|----------|--------|
| Creator: создать 2-stream кампанию | **VERIFIED** (campaign #2001 в прогоне) |
| Editor: Fetch → Add 2–5 → Pin/Remove/Restore → Cancel → Push → reload | **VERIFIED** |
| API parity (httpx) | **VERIFIED** |

**Скриншоты:**

- `/opt/cursor/artifacts/01-creator-tab-default.webp` — Creator (computerUse, [UI smoke + screenshots](bc-4e09d6d2-2fda-5602-acbd-aa777300d714)).
- `/opt/cursor/artifacts/02-editor-with-streams.webp` — Editor после Fetch, таблица офферов (тот же прогон; **без** Add/Pin/Cancel/Push/reload).
- `/opt/cursor/artifacts/02-creator-after-create.webp` — успешное создание (Playwright).
- `/opt/cursor/artifacts/03-editor-working-state.webp` — редактор после Push (clean).
- `/opt/cursor/artifacts/04-editor-after-reload.webp` — после перезагрузки страницы.

## Live readiness

План: [LIVE_QA.md](LIVE_QA.md). Live read-only — после credentials; **live mutation — NOT VERIFIED**.
## Публикационный снимок

Docker на машине подготовки публикации недоступен. Ранее compose проверялся в другом окружении **до** поздних изменений backend и здесь не повторялся. Актуальные числа тестов и live-статус см. [README.md](../README.md) и [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).
