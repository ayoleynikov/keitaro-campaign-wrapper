from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.keitaro.factory import get_keitaro_client
from app.keitaro.protocol import KeitaroClient
from app.services.campaign_service import CampaignService
from app.services.stream_editor_service import StreamEditorService


def get_client() -> KeitaroClient:
    return get_keitaro_client()


def get_campaign_service(
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_client),
) -> CampaignService:
    return CampaignService(client, db)


def get_stream_editor_service(
    db: Session = Depends(get_db),
    client: KeitaroClient = Depends(get_client),
) -> StreamEditorService:
    return StreamEditorService(client, db)