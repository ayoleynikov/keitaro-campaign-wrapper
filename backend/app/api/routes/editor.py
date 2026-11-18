from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_stream_editor_service
from app.domain.allocation import AllocationError
from app.keitaro.errors import KeitaroAuthError, KeitaroError, KeitaroTimeoutError, KeitaroValidationError, WriteGuardError
from app.services.stream_editor_service import StreamEditorService

router = APIRouter(tags=["editor"])


def _map_error(exc: KeitaroError) -> HTTPException:
    if isinstance(exc, KeitaroAuthError):
        return HTTPException(status_code=401, detail=str(exc))
    if isinstance(exc, KeitaroTimeoutError):
        return HTTPException(status_code=504, detail=str(exc))
    if isinstance(exc, WriteGuardError):
        return HTTPException(status_code=exc.status_code or 403, detail=str(exc))
    if isinstance(exc, KeitaroValidationError):
        return HTTPException(status_code=exc.status_code or 400, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


class AddOfferBody(BaseModel):
    offer_id: int = Field(..., gt=0)


class PinBody(BaseModel):
    share: int | None = Field(None, ge=0, le=100)


@router.post("/campaigns/{campaign_id}/fetch-streams")
async def fetch_streams(
    campaign_id: int,
    service: StreamEditorService = Depends(get_stream_editor_service),
) -> list[dict]:
    try:
        return await service.fetch_streams(campaign_id)
    except KeitaroError as exc:
        raise _map_error(exc) from exc


@router.get("/streams/{stream_id}/workspace")
def get_workspace(
    stream_id: int,
    service: StreamEditorService = Depends(get_stream_editor_service),
) -> dict:
    try:
        return service.get_workspace(stream_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/streams/{stream_id}/offers")
def add_offer(
    stream_id: int,
    body: AddOfferBody,
    service: StreamEditorService = Depends(get_stream_editor_service),
) -> dict:
    try:
        return service.add_offer(stream_id, body.offer_id)
    except AllocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/streams/{stream_id}/offers/{offer_id}")
def remove_offer(
    stream_id: int,
    offer_id: int,
    service: StreamEditorService = Depends(get_stream_editor_service),
) -> dict:
    try:
        return service.remove_offer(stream_id, offer_id)
    except AllocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/streams/{stream_id}/offers/{offer_id}/restore")
def restore_offer(
    stream_id: int,
    offer_id: int,
    service: StreamEditorService = Depends(get_stream_editor_service),
) -> dict:
    try:
        return service.restore_offer(stream_id, offer_id)
    except AllocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/streams/{stream_id}/offers/{offer_id}/pin")
def pin_offer(
    stream_id: int,
    offer_id: int,
    body: PinBody,
    service: StreamEditorService = Depends(get_stream_editor_service),
) -> dict:
    try:
        return service.pin_offer(stream_id, offer_id, body.share)
    except AllocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/streams/{stream_id}/offers/{offer_id}/pin")
def unpin_offer(
    stream_id: int,
    offer_id: int,
    service: StreamEditorService = Depends(get_stream_editor_service),
) -> dict:
    try:
        return service.unpin_offer(stream_id, offer_id)
    except AllocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/streams/{stream_id}/cancel")
def cancel(stream_id: int, service: StreamEditorService = Depends(get_stream_editor_service)) -> dict:
    return service.cancel(stream_id)


@router.post("/streams/{stream_id}/push")
async def push(stream_id: int, service: StreamEditorService = Depends(get_stream_editor_service)) -> dict:
    try:
        return await service.push(stream_id)
    except AllocationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeitaroError as exc:
        raise _map_error(exc) from exc