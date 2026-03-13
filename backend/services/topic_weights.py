from sqlalchemy.orm import Session
from models import DBUserTopicWeight, DBBenchmark
from datetime import datetime


def initialize_user_topic_weights(user_id: str, db: Session):
    """
    Creates initial topic weights for a user if they don't exist.
    Default weight = 1.0 for each topic present in benchmarks.
    """

    # Check if weights already exist
    existing = db.query(DBUserTopicWeight).filter(
        DBUserTopicWeight.userId == user_id
    ).first()

    if existing:
        return

    # Get all topics from benchmarks
    topics = db.query(DBBenchmark.topic).distinct().all()

    weights = []

    for t in topics:
        weights.append(
            DBUserTopicWeight(
                userId=user_id,
                topic=t[0],
                weight=1.0,
                lastUpdated=datetime.utcnow()
            )
        )

    if weights:
        db.add_all(weights)
        db.commit()