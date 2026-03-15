from sqlalchemy.orm import Session
from models import DBSubmission, DBProblem, DBUserTopicWeight
from datetime import datetime
from services.topic_weights import initialize_user_topic_weights

LEARNING_RATE = 0.2

def recalculate_user_topic_weights(user_id: str, contests: list, db: Session):
    # Ensure baseline topic weights exist
    initialize_user_topic_weights(user_id, db)
    
    # Reset weights to 1.0 before recalculating
    db.query(DBUserTopicWeight).filter(DBUserTopicWeight.userId == user_id).update({"weight": 1.0})
    db.commit()

    # Sort contests chronologically (oldest to newest) to apply EMA correctly
    contests_sorted = sorted(contests, key=lambda x: x.get("ratingUpdateTimeSeconds", 0))

    for contest in contests_sorted:
        contest_id = contest.get("contestId")
        new_rating = contest.get("newRating", 0)
        old_rating = contest.get("oldRating", 0)
        rating_change = new_rating - old_rating
        
        if contest_id:
            update_topic_weights_after_contest(user_id, contest_id, rating_change, db)

def update_topic_weights_after_contest(user_id: str, contest_id: int, rating_change: int, db: Session):
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

    alpha = LEARNING_RATE
    
    if rating_change > 0:
        topics_to_update = solved_topics
        boost = 1.0 + min(reward, 1.0) # Reward multiplier Cap at 2.0
    else:
        topics_to_update = unsolved_topics
        boost = 1.0 + min(abs(reward), 1.0) # Penalty highlight multiplier Cap at 2.0

    for topic in attempted_topics:
        weight_row = (
            db.query(DBUserTopicWeight)
            .filter(DBUserTopicWeight.userId == user_id)
            .filter(DBUserTopicWeight.topic == topic)
            .first()
        )

        if not weight_row:
            # Dynamically add topic if it didn't exist in benchmark initialization
            weight_row = DBUserTopicWeight(userId=user_id, topic=topic, weight=1.0)
            db.add(weight_row)

        if topic in topics_to_update:
            target_weight = weight_row.weight * boost
        else:
            target_weight = 1.0 # Decay un-impactful topics touched in this contest

        weight_row.weight = (1 - alpha) * weight_row.weight + alpha * target_weight
        weight_row.lastUpdated = datetime.utcnow()

    db.commit()