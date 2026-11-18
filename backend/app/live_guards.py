from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.keitaro.errors import WriteGuardError
from app.keitaro.protocol import KeitaroClient


def write_allowlist_name() -> str:
    return (get_settings().keitaro_write_allowlist_name or "").strip()


def assert_campaign_name_allowed(name: str) -> None:
    allowed = write_allowlist_name()
    if allowed and name != allowed:
        raise WriteGuardError(
            f"Writes are limited to the allowlisted campaign name {allowed!r}",
            status_code=403,
        )


async def assert_campaign_id_allowed(client: KeitaroClient, campaign_id: int) -> dict[str, Any]:
    campaign = await client.get_campaign(campaign_id)
    allowed = write_allowlist_name()
    if allowed and campaign.get("name") != allowed:
        raise WriteGuardError(
            "Campaign is outside the write allowlist",
            status_code=403,
        )
    return campaign


async def assert_stream_write_allowed(client: KeitaroClient, stream_id: int) -> dict[str, Any]:
    stream = await client.get_stream(stream_id)
    cid = int(stream["campaign_id"])
    await assert_campaign_id_allowed(client, cid)
    return stream
