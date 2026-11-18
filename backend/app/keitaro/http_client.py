from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroError,
    KeitaroTimeoutError,
    KeitaroValidationError,
    WriteGuardError,
)
from app.keitaro.payloads import as_resource_list, offer_id_of


def _normalize_api_root(base_url: str) -> tuple[str, str]:
    raw = base_url.strip().rstrip("/")
    if raw.endswith("/admin_api/v1"):
        origin = raw[: -len("/admin_api/v1")]
        api_root = raw + "/"
    else:
        origin = raw
        api_root = raw + "/admin_api/v1/"
    return origin, api_root


def _redact(text: str, secret: str) -> str:
    if not text:
        return text
    out = text
    if secret:
        out = out.replace(secret, "[REDACTED]")
    return out


class HttpKeitaroClient:
    """
    Live Keitaro Admin API client.
    Endpoints per https://admin-api.docs.keitaro.io/openapi.json (base: /admin_api/v1).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 30.0,
        allowed_origin: str | None = None,
        forbid_delete: bool = False,
    ) -> None:
        origin, api_root = _normalize_api_root(base_url)
        self._origin = (allowed_origin or origin).rstrip("/")
        self._api_root = api_root
        self._api_key = api_key
        self._timeout = timeout
        self._forbid_delete = forbid_delete
        self._assert_authorized_url(self._api_root)

    def _headers(self) -> dict[str, str]:
        return {"Api-Key": self._api_key, "Accept": "application/json", "Content-Type": "application/json"}

    def _assert_authorized_url(self, url: str) -> None:
        parsed = urlparse(url)
        allowed = urlparse(self._origin)
        if parsed.scheme != "https":
            raise WriteGuardError("Keitaro URL must be https", status_code=403)
        if parsed.netloc != allowed.netloc or allowed.scheme != "https":
            raise WriteGuardError("Keitaro URL is outside the allowed origin", status_code=403)
        if not parsed.path.startswith("/admin_api/v1"):
            raise WriteGuardError("Keitaro URL is outside /admin_api/v1", status_code=403)

    def _resolve_redirect(self, current: str, location: str) -> str:
        next_url = urljoin(current, location)
        self._assert_authorized_url(next_url)
        return next_url

    async def _request(self, method: str, path: str, *, json_body: Any | None = None) -> Any:
        url = urljoin(self._api_root, path.lstrip("/"))
        self._assert_authorized_url(url)
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=False) as client:
                response = None
                for _ in range(4):
                    response = await client.request(method, url, headers=self._headers(), json=json_body)
                    if response.status_code not in {301, 302, 303, 307, 308}:
                        break
                    location = response.headers.get("location")
                    if not location:
                        raise KeitaroError("Keitaro redirect missing Location")
                    try:
                        url = self._resolve_redirect(url, location)
                    except WriteGuardError as exc:
                        raise WriteGuardError(
                            "Blocked off-origin or unauthorized redirect; auth header was not followed",
                            status_code=403,
                        ) from exc
                else:
                    raise KeitaroError("Too many same-origin redirects")
        except WriteGuardError:
            raise
        except httpx.TimeoutException as exc:
            raise KeitaroTimeoutError("Keitaro request timed out") from exc
        except httpx.RequestError as exc:
            raise KeitaroError(f"Keitaro network error: {_redact(str(exc), self._api_key)}") from exc

        assert response is not None
        if response.status_code == 401:
            raise KeitaroAuthError("Invalid or missing Keitaro API key", status_code=401)
        if response.status_code == 403:
            raise WriteGuardError(
                f"Keitaro API error 403: {_redact(response.text[:500], self._api_key)}",
                status_code=403,
            )
        if response.status_code >= 400:
            detail = _redact(response.text[:500], self._api_key)
            raise KeitaroValidationError(
                f"Keitaro API error {response.status_code}: {detail}",
                status_code=response.status_code,
            )
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def list_domains(self) -> list[dict[str, Any]]:
        return await self._request("GET", "domains")

    async def list_groups(self, group_type: str = "campaigns") -> list[dict[str, Any]]:
        return await self._request("GET", f"groups?type={group_type}")

    async def list_traffic_sources(self) -> list[dict[str, Any]]:
        return await self._request("GET", "traffic_sources")

    async def list_offers(self) -> list[dict[str, Any]]:
        return as_resource_list(await self._request("GET", "offers"), what="offers")

    async def list_deleted_offers(self) -> list[dict[str, Any]]:
        return as_resource_list(await self._request("GET", "offers/deleted"), what="deleted offers")

    async def search_offers(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        offers = await self.list_offers()
        q = query.lower().strip()
        out: list[dict[str, Any]] = []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            oid = offer_id_of(offer)
            hay = f"{'' if oid is None else oid} {offer.get('name') or ''}".lower()
            if q and q in hay:
                out.append(offer)
            if len(out) >= limit:
                break
        return out

    async def list_campaigns(self, *, offset: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return await self._request("GET", f"campaigns?offset={offset}&limit={limit}")

    async def get_campaign(self, campaign_id: int) -> dict[str, Any]:
        return await self._request("GET", f"campaigns/{campaign_id}")

    async def create_campaign(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "campaigns", json_body=payload)

    async def update_campaign(self, campaign_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"campaigns/{campaign_id}", json_body=payload)

    async def delete_campaign(self, campaign_id: int) -> None:
        if self._forbid_delete:
            raise WriteGuardError("DELETE is forbidden in this QA configuration", status_code=403)
        await self._request("DELETE", f"campaigns/{campaign_id}")

    async def list_streams(self, campaign_id: int) -> list[dict[str, Any]]:
        return await self._request("GET", f"campaigns/{campaign_id}/streams")

    async def get_stream(self, stream_id: int) -> dict[str, Any]:
        return await self._request("GET", f"streams/{stream_id}")

    async def create_stream(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "streams", json_body=payload)

    async def update_stream(self, stream_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"streams/{stream_id}", json_body=payload)

    async def delete_stream(self, stream_id: int) -> None:
        if self._forbid_delete:
            raise WriteGuardError("DELETE is forbidden in this QA configuration", status_code=403)
        await self._request("DELETE", f"streams/{stream_id}")

    async def list_stream_filters(self) -> list[dict[str, Any]]:
        return await self._request("GET", "stream_filters")

    async def list_streams_actions(self) -> list[dict[str, Any]]:
        return await self._request("GET", "streams_actions")
