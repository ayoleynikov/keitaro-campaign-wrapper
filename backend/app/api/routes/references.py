from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_client
from app.keitaro.errors import KeitaroAuthError, KeitaroError, KeitaroTimeoutError, KeitaroValidationError
from app.keitaro.payloads import as_resource_list
from app.keitaro.protocol import KeitaroClient

router = APIRouter(prefix="/references", tags=["references"])


def _map_error(exc: KeitaroError) -> HTTPException:
    if isinstance(exc, KeitaroAuthError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, KeitaroTimeoutError):
        return HTTPException(status_code=504, detail=str(exc))
    if isinstance(exc, KeitaroValidationError):
        return HTTPException(status_code=exc.status_code or 400, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/domains")
async def domains(client: KeitaroClient = Depends(get_client)) -> list[dict]:
    try:
        return await client.list_domains()
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.get("/groups")
async def groups(
    group_type: str = Query("campaigns"),
    client: KeitaroClient = Depends(get_client),
) -> list[dict]:
    try:
        return await client.list_groups(group_type)
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.get("/traffic-sources")
async def traffic_sources(client: KeitaroClient = Depends(get_client)) -> list[dict]:
    try:
        return await client.list_traffic_sources()
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.get("/stream-filters")
async def stream_filters(client: KeitaroClient = Depends(get_client)) -> list[dict]:
    try:
        return await client.list_stream_filters()
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.get("/streams-actions")
async def streams_actions(client: KeitaroClient = Depends(get_client)) -> list[dict]:
    try:
        return await client.list_streams_actions()
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.get("/offers/search")
async def offers_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    client: KeitaroClient = Depends(get_client),
) -> list[dict]:
    try:
        return await client.search_offers(q, limit=limit)
    except KeitaroError as exc:
        raise _map_error(exc) from exc

@router.get("/offers/stats")
async def offers_stats(client: KeitaroClient = Depends(get_client)) -> dict:
    """Catalog size only (no offer names/payloads). Source: GET /offers and GET /offers/deleted."""
    try:
        offers = as_resource_list(await client.list_offers(), what="offers")
        deleted = as_resource_list(await client.list_deleted_offers(), what="deleted offers")
    except KeitaroError as exc:
        raise _map_error(exc) from exc
    return {"count": len(offers), "deleted_count": len(deleted)}
