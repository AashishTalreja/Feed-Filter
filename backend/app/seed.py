import logging

from sqlalchemy.orm import Session

from app import embeddings as emb
from app.categories import CATEGORIES
from app.models import Category

logger = logging.getLogger(__name__)


def seed_categories(db: Session) -> None:
    existing_keys = {row.key for row in db.query(Category.key).all()}
    if len(existing_keys) == len(CATEGORIES):
        return  # already seeded

    for key, data in CATEGORIES.items():
        if key in existing_keys:
            continue
        anchor_text = ". ".join(data["seed_phrases"])
        vector = emb.embed(anchor_text)
        db.add(Category(key=key, label=data["label"], embedding=vector))

    db.commit()
    logger.info("Seeded %d categories", len(CATEGORIES))
