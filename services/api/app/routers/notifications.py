from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import DriftNotification
from ..services import get_notifications, mark_notification_as_read

router = APIRouter(prefix="/api/v1", tags=["notifications"])


@router.get("/notifications/drift", response_model=list[DriftNotification])
def drift_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    only_unread: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[DriftNotification]:
    rows = get_notifications(db, limit=limit, offset=offset, only_unread=only_unread)
    return [
        DriftNotification(
            id=row.id,
            created_at=row.created_at,
            severity=row.severity,
            title=row.title,
            message=row.message,
            read=row.read,
        )
        for row in rows
    ]


@router.post("/notifications/drift/{notification_id}/read")
def mark_notification_read(
    notification_id: int, db: Session = Depends(get_db)
) -> dict[str, bool]:
    mark_notification_as_read(db, notification_id)
    return {"ok": True}

