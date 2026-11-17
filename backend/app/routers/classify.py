from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.classifier_pipeline import classify_video
from app.database import get_db
from app.models import TrustedChannel
from app.schemas import ClassifyRequest, ClassifyResponse

router = APIRouter(prefix="/classify", tags=["classify"])


@router.post("", response_model=ClassifyResponse)
def classify(req: ClassifyRequest, db: Session = Depends(get_db)):
    trusted = (
        db.query(TrustedChannel)
        .filter_by(user_id=req.user_id, channel=req.channel)
        .first()
    )
    if trusted:
        return ClassifyResponse(
            category=None, label=None, confidence=1.0, method="trusted_channel"
        )

    result = classify_video(db, req.title, req.channel, req.description, req.thumbnail_url)
    return ClassifyResponse(**result)
