# Опциональные safety-guard'ы

Все флаги задаются **только через окружение** (или локальный `.env`, который в git не входит). В коде **нет** зашитого имени тестовой кампании, ключа, hostname трекера или реальных id. Значения по умолчанию безопасны для mock-разработки: режим `mock`, пустой ключ, пустой allowlist, компенсация и DELETE не запрещены (как в обычном mock-сценарии).

| Переменная | По умолчанию | Назначение |
|------------|----------------|------------|
| `KEITARO_MODE` | `mock` | `mock` или `live` |
| `KEITARO_BASE_URL` | пусто | Origin трекера; клиент использует `{origin}/admin_api/v1` |
| `KEITARO_API_KEY` | пусто | Заголовок `Api-Key`. Не логируется и не отдаётся фронтенду |
| `KEITARO_ALLOWED_ORIGIN` | пусто | Если задан, разрешён только этот HTTPS origin; off-origin redirect с ключом не выполняется |
| `KEITARO_WRITE_ALLOWLIST_NAME` | пусто | Если задан, create/update и индекс кампаний ограничены **точным** именем кампании. Пустой — ограничение выключено |
| `KEITARO_CREATE_CAMPAIGN_STATE` | `active` | Состояние новой кампании (`active` или `disabled`) |
| `KEITARO_DISABLE_COMPENSATION` | `false` | Не удалять частично созданные объекты при сбое create |
| `KEITARO_FORBID_DELETE` | `false` | Клиент отказывается слать DELETE на Admin API |

Рекомендация для аккуратного live-прогона: `disabled` + allowlist точного test-имени + `DISABLE_COMPENSATION=true` + `FORBID_DELETE=true` + `ALLOWED_ORIGIN`. Это не заменяет осторожность: не направляйте ключ в документацию, архивы и frontend.

При ошибке live-write клиент не делает слепой повтор мутации и не компенсирует её DELETE, если компенсация/DELETE выключены. Частично созданная кампания, найденная по точному имени, сообщается как `PartialCreateError`.
