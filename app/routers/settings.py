from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserSettings
from app.schemas import SettingsIn, SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/{user_id}", response_model=SettingsOut)
def get_settings(user_id: str, db: Session = Depends(get_db)):
    row = db.query(UserSettings).filter_by(user_id=user_id).first()
    if not row:
        # sensible defaults for a first-time user
        return SettingsOut(user_id=user_id, enabled=False, allowed_categories=[], debug=False)
    return row


@router.put("/{user_id}", response_model=SettingsOut)
def upsert_settings(user_id: str, payload: SettingsIn, db: Session = Depends(get_db)):
    row = db.query(UserSettings).filter_by(user_id=user_id).first()
    if row is None:
        row = UserSettings(user_id=user_id)
        db.add(row)
    row.enabled = payload.enabled
    row.allowed_categories = payload.allowed_categories
    row.debug = payload.debug
    db.commit()
    db.refresh(row)
    return row
