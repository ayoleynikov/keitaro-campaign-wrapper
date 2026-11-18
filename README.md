# Keitaro Campaign Wrapper (тестовое задание)

Веб-обёртка над **Keitaro Admin API**: создание кампании с двумя потоками и редактор долей офферов в потоке.

- **Backend:** FastAPI, SQLAlchemy 2, Alembic, httpx
- **Frontend:** React + TypeScript (Vite)
- **Режимы Keitaro:** `mock` (детерминированные фикстуры, по умолчанию) и `live` (реальный трекер)

Подробные допущения и сверка с референс-видео: [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md). Опциональные write-guard'ы: [docs/SAFETY.md](docs/SAFETY.md). Заметки о live QA: [docs/LIVE_QA.md](docs/LIVE_QA.md).

## Что проверено, а что нет

Честно по слоям. **Live multi-offer Push не объявляется проверенным.**

| Область | Статус |
|---------|--------|
| Mock API + pytest | **да** — `46 passed` на момент подготовки публикации |
| Frontend `npm run build` | **да** |
| Миграции Alembic (локальный mock) | **да** |
| Live: создание одной кампании через приложение (disabled, 2 потока) | **да**, только после явного разрешения, только allowlisted test-имя |
| Live: Fetch Streams | **да** (та же кампания) |
| Live: локальный редактор Pin / Remove / Restore / Cancel; архив сохраняется после reload workspace | **да**, на единственном видимом оффере; upstream при этом не менялся |
| Live: Add нескольких различных офферов, доли 33/33/34 или pin 25 + 37/38, Push и сверка upstream | **нет** — у ключа был виден один оффер; новые глобальные офферы не создавались |
| Docker Compose на машине этой публикации | демон **недоступен**, не перепроверялось |
| Docker Compose ранее (другое cloud-окружение) | проходил **до** последующих изменений backend (write-guard'ы, разбор списков офферов); после этих правок compose здесь не гонялся |
| Публикация в GitHub / сдача работодателю | **не выполнены** в этом дереве (только локальная подготовка) |

Ключ API хранится только в переменных окружения бэкенда (`KEITARO_API_KEY`), не отдаётся во фронтенд и не должен попадать в git, логи или документацию.

## Архитектура

```
frontend (43123) --proxy /api--> backend (8801) --Admin API--> Keitaro
                                      |
                                 SQLite (operations + editor workspaces)
```

Редактор: **Fetch → локальный черновик (Pin/Add/Remove/Restore) → Push или Cancel**. Pin сам по себе upstream не пишет. Cancel откатывает workspace к baseline без мутаций Keitaro.

### SQLite (права и readonly)

Путь к БД разрешается относительно каталога `backend/`, не зависит от cwd. При старте проверяется возможность записи.

Если видите `attempt to write a readonly database` при живом `/api/health`: чаще всего uvicorn держит удалённый inode — **остановите** API и запустите снова; не удаляйте `backend/data/app.db` на работающем процессе. Альтернатива без потери данных: `DATABASE_URL=sqlite:////tmp/qa-copy.db` + `alembic upgrade head`. Подробнее: [docs/RELEASE_QA.md](docs/RELEASE_QA.md).

## Быстрый старт (локально, mock)

```bash
cp .env.example .env
# Оставьте KEITARO_MODE=mock. Не копируйте живые ключи в это дерево.

# Backend
cd backend
python3 -m venv ../.venv
../.venv/bin/pip install -r requirements.txt
mkdir -p data
PYTHONPATH=. ../.venv/bin/python -m alembic upgrade head
PYTHONPATH=. ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8801

# Frontend (другой терминал)
cd frontend
npm ci
npm run dev
```

Откройте http://127.0.0.1:43123 (вкладки Creator и Editor на `/`).

Проверка API: `curl http://127.0.0.1:8801/api/health` — ожидается `{"status":"ok","keitaro_mode":"mock"}`.

## Тесты и сборка фронта

```bash
cd backend
PYTHONPATH=. python3 -m pytest -q

cd ../frontend
npm ci
npm run build
```

## Миграции

```bash
cd backend
PYTHONPATH=. python3 -m alembic upgrade head
```

Схема: операции аудита и локальные workspace редактора (черновики, pin, removed/restore).

## Docker

```bash
cp .env.example .env
docker compose build
docker compose up -d
```

Данные SQLite в named volume `backend-data`. Фронт в compose проксирует `/api` на `http://backend:8801` (`VITE_DEV_API_PROXY`). Подробнее: [docs/RUN_LOCAL.md](docs/RUN_LOCAL.md).

На текущей машине подготовки публикации Docker **не установлен**. Ранее compose собирался в другом (cloud) окружении, но это было до поздних изменений backend и **не является** свежей проверкой этого снимка исходников.

## Live-режим

Только при явном разрешении и только против своего трекера. В `.env`:

```env
KEITARO_MODE=live
KEITARO_BASE_URL=https://your-tracker.example
KEITARO_API_KEY=...
# рекомендуется:
KEITARO_ALLOWED_ORIGIN=https://your-tracker.example
KEITARO_CREATE_CAMPAIGN_STATE=disabled
KEITARO_WRITE_ALLOWLIST_NAME=exact_test_campaign_name
KEITARO_DISABLE_COMPENSATION=true
KEITARO_FORBID_DELETE=true
```

Эндпоинты соответствуют [официальному OpenAPI](https://admin-api.docs.keitaro.io/openapi.json). Клиент ходит только на `{origin}/admin_api/v1`, без off-origin redirect с заголовком `Api-Key`.

Что из live уже делалось в рамках задания (без публикации чужих id/доменов): создание одной disabled-кампании, Fetch, локальный редактор на одном оффере. **Push распределения на нескольких офферах не проверялся.** Guard'ы по умолчанию выключены; их нужно включать явно через env. Описание: [docs/SAFETY.md](docs/SAFETY.md).

## Использование AI

Реализацию, тесты и документацию готовил LLM-ассистент вместе с автором. Live-запросы к трекеру выполнялись только после явного разрешения и только в оговорённом scope (одна test-кампания). Секреты в репозиторий не записывались.

## Лицензия и сдача

Этот каталог — локальная подготовка исходников. Публичный GitHub и отправка работодателю делаются отдельно, не из live-QA дерева и не с секретами/журналами.
