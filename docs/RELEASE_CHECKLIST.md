# Release checklist

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | `pytest -q` (backend, mock) | **VERIFIED** | 46 passed на момент подготовки публикации |
| 2 | `npm run build` (frontend) | **VERIFIED** | локальная сборка |
| 3 | Alembic `upgrade head` (mock DB) | **VERIFIED** | чистая копия staging/verify |
| 4 | Mock `/api/health` | **VERIFIED** | отдельный порт, `keitaro_mode=mock` |
| 5 | SQLite default path + recovery | **VERIFIED** | `test_sqlite_paths.py`, RELEASE_QA |
| 6 | Mock UI smoke | ранее **VERIFIED** (Playwright, mock) | не повторялся в шаге публикации |
| 7 | Docker `compose build/up` | ранее в cloud, **до** поздних правок backend | на этой машине демона нет, не перепроверялось |
| 8 | Архив без secrets/DB/node_modules/.git | **VERIFIED** | sanitized publish archive |
| 9 | Live creator + Fetch + local editor (один оффер) | **VERIFIED** (ограниченный scope) | docs/LIVE_QA.md, без чужих id в публичных docs |
| 10 | Live multi-offer Push (33/33/34, 25/37/38) | **NOT VERIFIED** | каталог ключа = 1 оффер |
| 11 | Employer form submit | **NOT DONE** | drafts only |
| 12 | Public GitHub push | **NOT DONE** | только локальный staging |
