# Допущения и сверка с референсом

## Источники

| Источник | Статус |
|----------|--------|
| [Keitaro OpenAPI](https://admin-api.docs.keitaro.io/openapi.json) | контракт адаптера |
| [Admin API overview](https://docs.keitaro.io/en/development/admin-api.html) | auth, методы |
| ТЗ (Notion / recovered spec) | функциональный scope |
| Видео [jNloscEWCjA](https://youtu.be/jNloscEWCjA) | **визуальная сверка редактора (2026-11-18)** |
| Live Keitaro работодателя | Пункт 1: allowlisted test campaign (disabled). Каталог офферов для ключа = 1. См. `docs/LIVE_QA.md`. Прочие кампании не менялись. |

Автотесты pytest **не заменяют** визуальную сверку UI; они проверяют backend/mock по задокументированным правилам.

## Округление долей (подтверждено по видео)

Для **незакреплённых** активных офферов в **текущем порядке строк**:

- `100 / N` → остаток у **последних** позиций: `33, 33, 34`; четыре оффера → `25×4`.
- После pin `25%` остаток `75` на двух офферах → `37, 38` (последний +1).
- Реализация: `split_even_last_gets_remainder()` в `app/domain/allocation.py`.

**Не показано в видео** (наша валидация, не утверждаем как «из видео»):

- Сумма pin &gt; 100 → 422.
- Все активные pin, сумма ≠ 100 → ошибка.
- Unpin пересчитывает доли; ручной ввод доли без pin — не реализован (только pin текущего share).

## State column (редактор)

| Ситуация | lifecycle | `state_label` | sync |
|----------|-----------|---------------|------|
| Активный | `active` | пусто | dirty/clean по draft |
| Локальный Remove (до Push) | `removed` | пусто | dirty |
| После Push локального remove | `archived` | пусто, Bring back | clean |
| Fetch: нет в KT | `removed` | `removed` (синий в референсе) | clean |

Поле `removed_origin`: `none` | `local` | `upstream`.

## Workflow (редактор)

1. **Fetch Streams** — `GET /campaigns/{id}/streams`, reconcile, baseline, белый заголовок.
2. **Add** — пересчёт, жёлтый заголовок, KT без изменений до Push.
3. **Push to KT** — `PUT /streams/{id}` только активные offers.
4. **Cancel** — откат к `baseline_json` (в т.ч. убрать неопубликованные привязки).
5. **Pin** — только в SQLAlchemy (`is_pinned`, `pinned_share`).

## Создание кампании

Два потока, `type=position`. Имя GEO-фильтра и `action_type` — из `GET /stream_filters` / `GET /streams_actions` (mock fixtures + live).

Illustrative examples в ТЗ (`FORTESTS`, `in.posdk.xyz`) **не обязательны**.

## Компенсация при создании

По умолчанию адаптер может удалить частично созданное при сбое. Для live QA включены `KEITARO_DISABLE_COMPENSATION` и `KEITARO_FORBID_DELETE`: при ошибке create процесс **останавливается**, повторный POST и compensating DELETE не выполняются. Частично созданный объект, если он найден по точному имени, сообщается как `PartialCreateError`.

## AI

Часть кода и документации подготовлена с LLM-ассистентом (Cursor Cloud Agent).