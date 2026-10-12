from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from src.api.routes.leads import get_session
from src.storage.models.alerts import SystemAlert
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class AlertPatch(BaseModel):
    status: Optional[str] = None
    delivery_status: Optional[str] = None

@router.get("")
async def get_alerts(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(50, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session)
):
    stmt = select(SystemAlert).order_by(desc(SystemAlert.detected_at)).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(SystemAlert.status == status)
    if priority:
        stmt = stmt.where(SystemAlert.priority == priority)
        
    result = await session.execute(stmt)
    alerts = result.scalars().all()
    
    return {
        "items": [
            {
                "id": a.id,
                "snapshot_id": a.snapshot_id,
                "lead_id": a.lead_id,
                "alert_type": a.alert_type,
                "priority": a.priority,
                "title": a.title,
                "message": a.message,
                "old_value": a.old_value,
                "new_value": a.new_value,
                "evidence": a.evidence_reference,
                "status": a.status,
                "detected_at": a.detected_at
            } for a in alerts
        ],
        "limit": limit,
        "offset": offset
    }

@router.get("/stats")
async def get_alert_stats(session: AsyncSession = Depends(get_session)):
    stmt = select(SystemAlert.status, func.count(SystemAlert.id)).group_by(SystemAlert.status)
    result = await session.execute(stmt)
    counts = dict(result.all())
    
    return {
        "total": sum(counts.values()),
        "by_status": counts
    }

@router.get("/{alert_id}")
async def get_alert(alert_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(SystemAlert).where(SystemAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    return {
        "id": alert.id,
        "snapshot_id": alert.snapshot_id,
        "lead_id": alert.lead_id,
        "alert_type": alert.alert_type,
        "priority": alert.priority,
        "title": alert.title,
        "message": alert.message,
        "old_value": alert.old_value,
        "new_value": alert.new_value,
        "evidence": alert.evidence_reference,
        "status": alert.status,
        "delivery_status": alert.delivery_status,
        "detected_at": alert.detected_at
    }

@router.patch("/{alert_id}")
async def update_alert(alert_id: str, payload: AlertPatch, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(SystemAlert).where(SystemAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    if payload.status:
        if payload.status not in ["NEW", "ACKNOWLEDGED", "ACTIONED", "DISMISSED", "EXPIRED"]:
            raise HTTPException(status_code=422, detail="Invalid status")
        alert.status = payload.status
        if payload.status in ["ACKNOWLEDGED"]:
            alert.acknowledged_at = func.now()
        if payload.status in ["ACTIONED"]:
            alert.actioned_at = func.now()
            
    if payload.delivery_status:
        alert.delivery_status = payload.delivery_status
        
    await session.commit()
    return {"status": "SUCCESS", "alert_id": alert.id, "new_status": alert.status}
