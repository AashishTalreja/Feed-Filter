from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TrustedChannel
from app.schemas import TrustRequest, TrustedChannelOut

router = APIRouter(prefix="/trust", tags=["trust"])


@router.post("", response_model=TrustedChannelOut)
def trust_channel(req: TrustRequest, db: Session = Depends(get_db)):
    existing = (
        db.query(TrustedChannel)
        .filter_by(user_id=req.user_id, channel=req.channel)
        .first()
    )
    if existing:
        return existing

    row = TrustedChannel(user_id=req.user_id, channel=req.channel)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{user_id}", response_model=list[TrustedChannelOut])
def list_trusted_channels(user_id: str, db: Session = Depends(get_db)):
    return db.query(TrustedChannel).filter_by(user_id=user_id).all()


@router.delete("/{user_id}/{channel}")
def untrust_channel(user_id: str, channel: str, db: Session = Depends(get_db)):
    db.query(TrustedChannel).filter_by(user_id=user_id, channel=channel).delete()
    db.commit()
    return {"ok": True}
