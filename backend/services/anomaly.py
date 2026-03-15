from sqlalchemy.orm import Session
from sqlalchemy import func
from models import DBSubmission, DBProblem

def detect_concept_gap_anomalies(user_id: str, contest_id: int, db: Session):
    """
    Analyzes submissions from a specific contest and flags Concept Gap Anomalies
    if a user took significantly longer than their historical average for similar problems.
    """
    # 1. Fetch user's OK submissions from the target contest
    recent_subs = (
        db.query(DBSubmission, DBProblem)
        .join(DBProblem, DBSubmission.problemId == DBProblem.problemId)
        .filter(DBSubmission.userId == user_id)
        .filter(DBSubmission.contestId == contest_id)
        .filter(DBSubmission.verdict == "OK")
        .filter(DBSubmission.timeToSolve.isnot(None))
        .all()
    )

    anomalies = []

    for sub, prob in recent_subs:
        current_time = sub.timeToSolve
        rating = prob.rating
        tags = prob.tags if prob.tags else ["general"]
        
        # We need a valid rating to compare against buckets
        if not rating or rating == 0:
            continue
            
        # Define a rating bucket (e.g., +/- 100 rating points)
        min_rating = rating - 100
        max_rating = rating + 100

        # Calculate historical average timeToSolve for similar rating and ANY matching tag
        historical_stats = (
            db.query(func.avg(DBSubmission.timeToSolve))
            .join(DBProblem, DBSubmission.problemId == DBProblem.problemId)
            .filter(DBSubmission.userId == user_id)
            .filter(DBSubmission.verdict == "OK")
            .filter(DBSubmission.timeToSolve.isnot(None))
            .filter(DBSubmission.contestId != contest_id) # Exclude current contest
            .filter(DBProblem.rating >= min_rating)
            .filter(DBProblem.rating <= max_rating)
            .filter(DBProblem.tags.op('?|')(tags)) # Postgres JSONB overlaps operator (For SQLite this would need custom logic, assuming PG here based on UUIDs/JSON in models)
            .scalar()
        )
        
        # Note: If using SQLite, the JSON operator ?| won't work perfectly. 
        # A simpler approach for compatibility (or if JSON operator fails) is to fetch and filter in Python
        if historical_stats is None:
            # Fallback for SQLite or if DB-level JSON array intersection isn't supported
            # Fetch all past valid submissions in rating bucket
            past_subs = (
                db.query(DBSubmission.timeToSolve, DBProblem.tags)
                .join(DBProblem, DBSubmission.problemId == DBProblem.problemId)
                .filter(DBSubmission.userId == user_id)
                .filter(DBSubmission.verdict == "OK")
                .filter(DBSubmission.timeToSolve.isnot(None))
                .filter(DBSubmission.contestId != contest_id)
                .filter(DBProblem.rating >= min_rating)
                .filter(DBProblem.rating <= max_rating)
                .all()
            )
            
            valid_times = []
            for p_time, p_tags in past_subs:
                p_tags = p_tags if p_tags else []
                # Check for tag intersection
                if set(tags).intersection(set(p_tags)):
                    valid_times.append(p_time)
                    
            if valid_times:
                historical_stats = sum(valid_times) / len(valid_times)

        # 3. Anomaly Criteria: 
        # If they took at least 5 minutes overall AND it's > 2x their historical average
        if historical_stats and current_time >= 5 and current_time > (historical_stats * 2):
            anomalies.append({
                "problemId": prob.problemId,
                "name": prob.name,
                "rating": rating,
                "tags": tags,
                "actual_timeToSolve": current_time,
                "historical_avg_time": round(historical_stats, 2),
                "wrongAttempts": sub.wrongAttempts,
                "anomaly_type": "Concept Gap Anomaly"
            })

    return {"contestId": contest_id, "anomalies_detected": anomalies}
