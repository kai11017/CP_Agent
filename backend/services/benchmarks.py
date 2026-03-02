import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import DBUserSkill, DBPlatformProfile, DBBenchmark
from datetime import datetime

def compute_benchmarks_for_bucket(min_rating: int, max_rating: int, db: Session):
    """
    Calculates skill statistics for all users within a specific rating bucket.
    """
    bucket_label = f"{min_rating}-{max_rating}"
    
    # 1. Get all user IDs who fall into this rating bucket
    user_ids = (
        db.query(DBPlatformProfile.userId)
        .filter(DBPlatformProfile.currentRating >= min_rating)
        .filter(DBPlatformProfile.currentRating <= max_rating)
        .all()
    )
    user_ids = [u[0] for u in user_ids]

    if not user_ids:
        return {"message": f"No users found in bucket {bucket_label}"}

    # 2. Fetch all skill scores for these users, grouped by topic
    from collections import defaultdict
    
    all_user_skills = (
        db.query(DBUserSkill.topic, DBUserSkill.score)
        .filter(DBUserSkill.userId.in_(user_ids))
        .all()
    )
    
    topic_data = defaultdict(list)
    for topic, score in all_user_skills:
        topic_data[topic].append(score)
        
    topic_data = list(topic_data.items())

    # 3. Calculate Stats & Save
    db.query(DBBenchmark).filter(DBBenchmark.ratingBucket == bucket_label).delete()

    for topic, scores in topic_data:
        avg_score = float(np.mean(scores))
        p75 = float(np.percentile(scores, 75))
        p90 = float(np.percentile(scores, 90))

        benchmark_entry = DBBenchmark(
            platform="codeforces",
            ratingBucket=bucket_label,
            topic=topic,
            avgScore=round(avg_score, 2),
            p75Score=round(p75, 2),
            p90Score=round(p90, 2),
            lastComputed=datetime.utcnow()
        )
        db.add(benchmark_entry)

    db.commit()
    return {"status": "success", "bucket": bucket_label, "topics_updated": len(topic_data)}