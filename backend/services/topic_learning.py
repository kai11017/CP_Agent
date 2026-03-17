from sqlalchemy.orm import Session
from models import DBUserTopicWeight, DBUserContestProblem
from datetime import datetime


LEARNING_RATE = 0.2


def update_topic_weights_after_contest(user_id: str, contest_id: int, rating_change: int, db: Session):
    """
    Updates topic weights based on contest outcome.
    - Rating UP: decrease weight for solved topics (already strong),
                 increase weight for unsolved topics (still a weakness).
    - Rating DOWN: increase weight for unsolved topics (caused the drop).

    Higher weight = higher priority for practice.
    """

    # Normalize reward
    reward = abs(rating_change) / 100.0

    # Use the pre-aggregated contest problem data
    contest_problems = (
        db.query(DBUserContestProblem)
        .filter(DBUserContestProblem.userId == user_id)
        .filter(DBUserContestProblem.contestId == contest_id)
        .all()
    )

    if not contest_problems:
        return

    solved_topics = set()
    unsolved_topics = set()

    for cp in contest_problems:
        tags = cp.tags if cp.tags else ["general"]

        if cp.solved:
            for tag in tags:
                solved_topics.add(tag)
        else:
            for tag in tags:
                unsolved_topics.add(tag)

    # Remove overlap — if a topic appears in both solved and unsolved,
    # it means user solved some problems but not others in that topic
    pure_unsolved = unsolved_topics - solved_topics

    if rating_change > 0:
        # Rating went UP: user is strong in solved topics, weak in unsolved
        for topic in solved_topics:
            _adjust_weight(user_id, topic, -LEARNING_RATE * reward * 0.5, db)
        for topic in pure_unsolved:
            _adjust_weight(user_id, topic, LEARNING_RATE * reward, db)
    else:
        # Rating went DOWN: unsolved topics caused the problem
        for topic in pure_unsolved:
            _adjust_weight(user_id, topic, LEARNING_RATE * reward * 1.5, db)
        for topic in solved_topics:
            _adjust_weight(user_id, topic, LEARNING_RATE * reward * 0.3, db)

    db.commit()


def _adjust_weight(user_id: str, topic: str, delta: float, db: Session):
    """
    Helper: adjusts a single topic weight by delta.
    Creates the weight row if it doesn't exist.
    Clamps weight to [0.1, 5.0] to prevent runaway values.
    """
    weight_row = (
        db.query(DBUserTopicWeight)
        .filter(DBUserTopicWeight.userId == user_id)
        .filter(DBUserTopicWeight.topic == topic)
        .first()
    )

    if weight_row:
        weight_row.weight = max(0.1, min(5.0, weight_row.weight + delta))
        weight_row.lastUpdated = datetime.utcnow()
    else:
        # Create new weight row
        new_weight = DBUserTopicWeight(
            userId=user_id,
            topic=topic,
            weight=max(0.1, min(5.0, 1.0 + delta)),
            lastUpdated=datetime.utcnow()
        )
        db.add(new_weight)