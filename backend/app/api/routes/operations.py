from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.operation import Operation

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("/{operation_id}")
def get_operation(operation_id: int, db: Session = Depends(get_db)) -> dict:
    op = db.get(Operation, operation_id)
    if not op:
        raise HTTPException(status_code=404, detail="Operation not found")
    return {
        "id": op.id,
        "kind": op.kind,
        "status": op.status,
        "keitaro_campaign_id": op.keitaro_campaign_id,
        "created_resource_ids": op.created_resource_ids,
        "error_message": op.error_message,
        "created_at": op.created_at.isoformat() if op.created_at else None,
    }