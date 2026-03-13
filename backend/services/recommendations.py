from sqlalchemy.orm import Session
from models import DBUserSkill, DBBenchmark, DBPlatformProfile, DBProblem, DBSubmission, DBUserTopicWeight
import random


def get_problem_recommendations(user_id: str, db: Session):

    # 1. Get user profile
    profile = db.query(DBPlatformProfile).filter(DBPlatformProfile.userId == user_id).first()
    if not profile:
        return {"error": "Profile not found"}

    rating = profile.currentRating if profile.currentRating and profile.currentRating > 0 else 1200
    bucket = f"{(rating // 200) * 200}-{(rating // 200) * 200 + 199}"

    # 2. Fetch user skills
    user_skills = {
        s.topic: s.score
        for s in db.query(DBUserSkill).filter(DBUserSkill.userId == user_id).all()
    }

    # 3. Fetch benchmark data
    benchmarks = {
        b.topic: b.avgScore
        for b in db.query(DBBenchmark).filter(DBBenchmark.ratingBucket == bucket).all()
    }

    # 4. Fetch learned topic weights
    topic_weights = {
        w.topic: w.weight
        for w in db.query(DBUserTopicWeight).filter(DBUserTopicWeight.userId == user_id).all()
    }

    # 5. Find topic with highest PRIORITY
    weakest_topic = None
    max_priority = -999999
    max_gap = 0

    for topic, bench_score in benchmarks.items():

        user_score = user_skills.get(topic, 0)
        gap = bench_score - user_score

        weight = topic_weights.get(topic, 1.0)

        priority = gap * weight

        if priority > max_priority:
            max_priority = priority
            weakest_topic = topic
            max_gap = gap

    if not weakest_topic:
        weakest_topic = "math"

    # 6. Get solved problems
    solved_records = db.query(DBSubmission.problemId).filter(
        DBSubmission.userId == user_id,
        DBSubmission.verdict == "OK"
    ).all()

    solved_ids = {s[0] for s in solved_records}

    # 7. Target rating range
    target_min = rating
    target_max = rating + 300

    candidate_problems = db.query(DBProblem).filter(
        DBProblem.rating >= target_min,
        DBProblem.rating <= target_max
    ).all()

    recommended = []

    random.shuffle(candidate_problems)

    for prob in candidate_problems:

        if prob.problemId not in solved_ids:

            if prob.tags and weakest_topic in prob.tags:

                match_idx = next(
                    (i for i, c in enumerate(prob.problemId) if c.isalpha()),
                    len(prob.problemId)
                )

                cf_url = f"https://codeforces.com/problemset/problem/{prob.problemId[:match_idx]}/{prob.problemId[match_idx:]}"

                recommended.append({
                    "problemId": prob.problemId,
                    "name": prob.name,
                    "rating": prob.rating,
                    "tags": prob.tags,
                    "link": cf_url
                })

        if len(recommended) >= 3:
            break

    return {
        "handle": profile.handle,
        "focus_topic": weakest_topic,
        "reason": f"Your score in '{weakest_topic}' is {max_gap:.0f} points behind the benchmark. Priority adjusted using learned topic weights.",
        "recommendations": recommended
    }