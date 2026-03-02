from sqlalchemy.orm import Session
from collections import defaultdict
from models import DBSubmission, DBProblem, DBUserSkill
from datetime import datetime

def calculate_problem_weight(rating: int) -> float:
    """
    Uses an exponential curve to reward harder problems significantly more.
    """
    if not rating or rating < 800:
        rating = 800  # Baseline for unrated/very easy problems
        
    # Formula: (Rating / 1000)^3 * 20
    return ((rating / 1000.0) ** 3) * 20.0

def calculate_diminishing_returns(scores: list) -> float:
    """
    Sorts scores high to low and applies diminishing weights
    so solving 100 easy problems doesn't equal solving 1 hard problem.
    """
    scores.sort(reverse=True)
    total_score = 0.0
    for i, score in enumerate(scores):
        total_score += score * (0.9 ** i)  # Each subsequent problem gives 10% less value
    return round(total_score, 2)

def compute_user_vector(user_id: str, db: Session) -> dict:
    """
    Calculates the user's skill vector using exponential weights and diminishing returns.
    """
    solved_records = (
        db.query(DBSubmission, DBProblem)
        .join(DBProblem, DBSubmission.problemId == DBProblem.problemId)
        .filter(DBSubmission.userId == user_id)
        .filter(DBSubmission.verdict == "OK")
        .all()
    )

    # 1. Group problem scores by topic
    topic_scores = defaultdict(list)
    processed_problems = set()

    for sub, prob in solved_records:
        if prob.problemId in processed_problems:
            continue
        processed_problems.add(prob.problemId)

        # Calculate the base weight for this specific problem's rating
        weight = calculate_problem_weight(prob.rating)
        
        # Contest Multiplier (from Blueprint, default 1.0 for now)
        multiplier = 1.0 
        final_problem_score = weight * multiplier

        tags = prob.tags if prob.tags else ["general"]
        for tag in tags:
            topic_scores[tag].append(final_problem_score)

    # Calculate final scores with diminishing returns
    final_skills = {}
    for tag, scores in topic_scores.items():
        final_skills[tag] = calculate_diminishing_returns(scores)

    # Sort topics by score descending
    sorted_skills = dict(sorted(final_skills.items(), key=lambda item: item[1], reverse=True))

    db.query(DBUserSkill).filter(DBUserSkill.userId == user_id).delete()
        
    db_skills = []
    for tag, score in sorted_skills.items():
        db_skills.append(DBUserSkill(
            userId=user_id,
            topic=tag,
            score=score,
            lastUpdated=datetime.utcnow()
        ))
    
    if db_skills:
        db.add_all(db_skills)
        db.commit()
        
    return {
        "user_id": user_id,
        "total_unique_solved": len(processed_problems),
        "skill_vector": sorted_skills
    }
