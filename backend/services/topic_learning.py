from sqlalchemy.orm import Session
from models import DBSubmission, DBProblem, DBUserTopicWeight
from datetime import datetime


LEARNING_RATE = 0.2


def update_topic_weights_after_contest(user_id: str, contest_id: int, rating_change: int, db: Session):

    # Normalize reward
    reward = rating_change / 100.0

    submissions = (
        db.query(DBSubmission, DBProblem)
        .join(DBProblem, DBSubmission.problemId == DBProblem.problemId)
        .filter(DBSubmission.userId == user_id)
        .filter(DBSubmission.contestId == contest_id)
        .all()
    )

    if not submissions:
        return

    solved_topics = set()
    attempted_topics = set()

    for sub, prob in submissions:

        tags = prob.tags if prob.tags else ["general"]

        for tag in tags:
            attempted_topics.add(tag)

        if sub.verdict == "OK":
            for tag in tags:
                solved_topics.add(tag)

    unsolved_topics = attempted_topics - solved_topics

    # Two learning cases

    if rating_change > 0:
        topics_to_update = solved_topics
    else:
        topics_to_update = unsolved_topics
        reward = abs(reward)

    for topic in topics_to_update:

        weight_row = (
            db.query(DBUserTopicWeight)
            .filter(DBUserTopicWeight.userId == user_id)
            .filter(DBUserTopicWeight.topic == topic)
            .first()
        )

        if weight_row:
            weight_row.weight += LEARNING_RATE * reward
            weight_row.lastUpdated = datetime.utcnow()

    db.commit()