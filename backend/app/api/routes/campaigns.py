from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_campaign_service, get_client
from app.domain.allocation import AllocationError
from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroError,
    KeitaroTimeoutError,
    KeitaroValidationError,
    PartialCreateError,
    WriteGuardError,
)
from app.schemas.campaigns import (
    CampaignCreateResponse,
    CreateCampaignRequest,
    UpdateStreamOffersRequest,
)
from app.live_guards import write_allowlist_name
from app.services.campaign_service import CampaignService
from app.keitaro.protocol import KeitaroClient

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _map_error(exc: KeitaroError) -> HTTPException:
    if isinstance(exc, KeitaroAuthError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, KeitaroTimeoutError):
        return HTTPException(status_code=504, detail=str(exc))
    if isinstance(exc, PartialCreateError):
        return HTTPException(status_code=exc.status_code or 409, detail=str(exc))
    if isinstance(exc, WriteGuardError):
        return HTTPException(status_code=exc.status_code or 403, detail=str(exc))
    if isinstance(exc, KeitaroValidationError):
        return HTTPException(status_code=exc.status_code or 400, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@router.get("")
async def list_campaigns(
    name: str | None = Query(None, description="Exact campaign name lookup (pages upstream)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    client: KeitaroClient = Depends(get_client),
    service: CampaignService = Depends(get_campaign_service),
) -> list[dict]:
    try:
        if name:
            found = await service.find_campaign_by_name(name)
            return [found] if found else []
        # When a write allowlist is active, do not list unrelated campaigns for the UI.
        allowed = write_allowlist_name()
        if allowed:
            found = await service.find_campaign_by_name(allowed)
            return [found] if found else []
        return await client.list_campaigns(offset=offset, limit=limit)
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.post("", response_model=CampaignCreateResponse)
async def create_campaign(
    body: CreateCampaignRequest,
    service: CampaignService = Depends(get_campaign_service),
) -> CampaignCreateResponse:
    try:
        op, result = await service.create_campaign_with_streams(body.model_dump())
    except KeitaroError as exc:
        raise _map_error(exc) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return CampaignCreateResponse(
        operation_id=op.id,
        campaign_id=int(result["campaign"]["id"]),
        streams=result["streams"],
    )


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: int,
    client: KeitaroClient = Depends(get_client),
) -> dict:
    try:
        return await client.get_campaign(campaign_id)
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.get("/{campaign_id}/streams")
async def list_streams(
    campaign_id: int,
    client: KeitaroClient = Depends(get_client),
) -> list[dict]:
    try:
        return await client.list_streams(campaign_id)
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.put("/streams/{stream_id}/offers")
async def update_stream_offers_legacy(
    stream_id: int,
    body: UpdateStreamOffersRequest,
    service: CampaignService = Depends(get_campaign_service),
) -> dict:
    """Legacy direct PUT — prefer editor push/cancel workflow."""
    pairs = [(item.offer_id, item.weight) for item in body.offers]
    try:
        updated = await service.update_stream_offers(stream_id, pairs)
    except AllocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeitaroError as exc:
        raise _map_error(exc) from exc
    return {"stream_id": stream_id, "offers": updated.get("offers", [])}