# backend/services/analytics.py

from sqlalchemy.orm import Session
from models import DBUserSkill, DBBenchmark, DBPlatformProfile


# 🔥 Canonical important topics (UI controlled)
IMPORTANT_TOPICS = [
    "arrays",
    "two pointers",
    "sliding window",
    "stack",
    "queues",
    "linked list",
    "trees",
    "binary search",
    "binary search trees",
    "dp",
    "graphs",
    "greedy",
    "recursion",
    "tries",
    "math",
    "strings"
]


def get_user_topic_dashboard(user_id: str, db: Session):
    """
    Returns clean topic-wise comparison for IMPORTANT topics.
    This is purely for UI display.
    """

    # 1. Get user profile
    profile = db.query(DBPlatformProfile).filter(
        DBPlatformProfile.userId == user_id
    ).first()

    if not profile:
        return {"error": "User profile not found"}

    rating = profile.currentRating if profile.currentRating else 1200

    # 2. Determine rating bucket
    bucket_low = (rating // 200) * 200
    bucket_high = bucket_low + 199
    bucket = f"{bucket_low}-{bucket_high}"

    # 3. Fetch user skills
    user_skills = {
        s.topic.lower(): s.score
        for s in db.query(DBUserSkill).filter(
            DBUserSkill.userId == user_id
        ).all()
    }

    # 4. Fetch benchmark
    benchmarks = {
        b.topic.lower(): b.avgScore
        for b in db.query(DBBenchmark).filter(
            DBBenchmark.ratingBucket == bucket
        ).all()
    }

    # 5. Build dashboard for IMPORTANT topics only
    dashboard = []

    for topic in IMPORTANT_TOPICS:

        user_score = user_skills.get(topic, 0)
        bench_score = benchmarks.get(topic, 0)

        gap = bench_score - user_score  # positive = weak

        dashboard.append({
            "topic": topic,
            "user_score": round(user_score, 2),
            "benchmark_avg": round(bench_score, 2),
            "gap": round(gap, 2),
            "status": (
                "Weak" if gap > 20 else
                "Strong" if gap < -20 else
                "Average"
            )
        })

    # 6. Sort → weakest first (highest gap)
    dashboard.sort(key=lambda x: x["gap"], reverse=True)

    return {
        "handle": profile.handle,
        "rating": rating,
        "bucket": bucket,
        "topics": dashboard
    }