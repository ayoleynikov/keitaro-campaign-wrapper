# Черновики для формы работодателя (не отправлять автоматически)

## Использование AI

> Реализацию выполнял с LLM-ассистентом (scaffold FastAPI/React, адаптер Admin API по OpenAPI, редактор по референс-видео, тесты, Docker-файлы, документация). Live-проверки — только после явного разрешения и только на одной allowlisted test-кампании: создание (disabled, 2 потока), Fetch, локальный редактор (Pin/Remove/Restore/Cancel). Push распределения на нескольких офферах не выполнялся (в каталоге ключа был один оффер; новые офферы не создавались). Секреты и идентификаторы трекера в репозиторий не входят.

## Что проверено

- Mock end-to-end: создание 2-stream кампании, редактор (fetch/draft/push/cancel/pins) в mock, **46** pytest, `npm run build`.
- UI smoke (dev) ранее: Playwright + скриншоты (mock id, не live).
- Docker Compose: проходил в отдельном cloud-окружении **до** последующих изменений backend; на машине этой подготовки демон недоступен, снимок заново не собирался.
- Live (ограниченный scope): creator + Fetch + локальный editor на одном существующем оффере. Кампания оставлена disabled.

## Что не проверено / ограничения

- **Live multi-offer Push** (33/33/34, pin 25 + 37/38, сверка upstream после Push) — **NOT VERIFIED**.
- Полное визуальное совпадение редактора с live UI Keitaro — нет (сверка с видео и mock).

## Placeholders для настроек live (подставить у себя локально, не коммитить)

```env
KEITARO_MODE=live
KEITARO_BASE_URL=https://<your-tracker-host>
KEITARO_API_KEY=<secret>
KEITARO_ALLOWED_ORIGIN=https://<your-tracker-host>
KEITARO_WRITE_ALLOWLIST_NAME=<exact_test_campaign_name>
KEITARO_CREATE_CAMPAIGN_STATE=disabled
KEITARO_DISABLE_COMPENSATION=true
KEITARO_FORBID_DELETE=true
```
