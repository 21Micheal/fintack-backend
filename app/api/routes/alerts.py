from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models.transaction import Alert  # adjust path
from app.schemas.alert import AlertCreate, AlertOut, AlertUpdate  # recommended: use Pydantic
from app.utils.alerts import generate_alerts_for_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.post("/", response_model=AlertOut)
def create_alert(
    alert_in: AlertCreate,
    db: Session = Depends(get_db)
):
    db_alert = Alert(**alert_in.dict())
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert

@router.get("/{user_id}", response_model=List[AlertOut])
def get_user_alerts(
    user_id: str,
    db: Session = Depends(get_db),
    limit: int = 50,
    unread_only: bool = False
):
    query = db.query(Alert).filter(Alert.user_id == user_id)
    if unread_only:
        query = query.filter(Alert.is_read == False)
    return query.order_by(Alert.created_at.desc()).limit(limit).all()

@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    alert_update: AlertUpdate,
    db: Session = Depends(get_db)
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    
    update_data = alert_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(alert, field, value)
    
    db.commit()
    db.refresh(alert)
    return alert

@router.post("/generate/{user_id}")
def trigger_generate_alerts(user_id: str, db: Session = Depends(get_db)):
    new_alerts = generate_alerts_for_user(user_id, db)
    return {
        "message": f"Generated {len(new_alerts)} new alert(s)",
        "count": len(new_alerts),
        "new_alerts": new_alerts[:5]  # limit preview
    }

@router.post("/{alert_id}/mark-read")
def mark_single_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.is_read = True
    db.commit()
    db.refresh(alert)
    return alert

@router.post("/mark-all-read/{user_id}")
def mark_all_read(user_id: str, db: Session = Depends(get_db)):
    updated = (
        db.query(Alert)
        .filter(Alert.user_id == user_id, Alert.is_read == False)
        .update({"is_read": True})
    )
    db.commit()
    return {"message": f"Marked {updated} alerts as read"}