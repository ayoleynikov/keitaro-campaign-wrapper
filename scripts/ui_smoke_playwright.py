#!/usr/bin/env python3
"""Mock UI smoke via Playwright; saves screenshots to /opt/cursor/artifacts/."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:43123"
OUT = Path("/opt/cursor/artifacts")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(BASE, wait_until="networkidle")

        # Creator
        page.get_by_role("textbox", name="Название кампании").fill("Smoke QA Two-Stream")
        page.get_by_role("textbox", name="GEO (ISO-3166 alpha-2)").fill("US")
        page.get_by_label("Домен").select_option(index=1)
        page.get_by_label("Группа кампаний").select_option(index=1)
        page.get_by_label("Источник трафика").select_option(index=1)
        page.get_by_label(re.compile("Оффер")).fill("1")
        page.get_by_role("button", name=re.compile("Создать")).click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "02-creator-after-create.webp"), full_page=True)

        success_loc = page.locator("p.success")
        result = success_loc.inner_text() if success_loc.count() else ""
        m = re.search(r"#(\d+)", result)
        campaign_id = m.group(1) if m else ""

        # Editor
        page.get_by_role("button", name="Редактор").click()
        page.wait_for_timeout(400)
        if campaign_id:
            page.locator("label").filter(has_text="Кампания").locator("select").select_option(campaign_id)
        else:
            page.locator("label").filter(has_text="Кампания").locator("select").select_option(index=1)
        page.get_by_role("button", name="Fetch Streams from KT").click()
        page.wait_for_timeout(600)
        page.locator("label").filter(has_text="Поток").locator("select").select_option(index=1)
        page.wait_for_timeout(400)

        for oid in ("2", "3", "4", "5"):
            page.get_by_placeholder("ID оффера").fill(oid)
            page.get_by_role("button", name="Add offer").click()
            page.wait_for_timeout(350)

        # Pin / Remove / Restore on second active row
        page.get_by_role("button", name="Pin").nth(1).click()
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Remove", exact=True).nth(1).click()
        page.wait_for_timeout(300)
        if page.get_by_role("button", name="Bring back").count():
            page.get_by_role("button", name="Bring back").first.click()
            page.wait_for_timeout(300)

        page.get_by_role("button", name="Cancel", exact=True).click()
        page.wait_for_timeout(400)
        page.get_by_placeholder("ID оффера").fill("4")
        page.get_by_role("button", name="Add offer").click()
        page.wait_for_timeout(400)
        page.get_by_role("button", name="Push to KT").click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "03-editor-working-state.webp"), full_page=True)

        page.reload(wait_until="networkidle")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "04-editor-after-reload.webp"), full_page=True)

        browser.close()
        print("campaign_id", campaign_id or "unknown")
        print("screenshots", OUT / "02-creator-after-create.webp", OUT / "03-editor-working-state.webp")
    return 0


if __name__ == "__main__":
    sys.exit(main())