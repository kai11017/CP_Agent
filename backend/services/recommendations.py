# backend/services/recommendation.py

from sqlalchemy.orm import Session
from models import DBProblem, DBSubmission, DBPlatformProfile
from services.gap_analysis import get_topic_weakness_report
from services.ai_coach import generate_ai_feedback

def get_problem_recommendations(user_id: str, db: Session):

    # 1. Get profile
    profile = db.query(DBPlatformProfile).filter(
        DBPlatformProfile.userId == user_id
    ).first()

    if not profile:
        return {"error": "Profile not found"}

    rating = profile.currentRating if profile.currentRating else 1200

    # 2. Get weakness report (🔥 SINGLE SOURCE OF TRUTH)
    weakness_data = get_topic_weakness_report(user_id, db)

    if "weaknesses" not in weakness_data:
        return {"error": "Could not compute weaknesses"}

    # 🔥 pick top 5 weak topics
    weak_topics = weakness_data["weaknesses"][:5]

    # 3. Get solved problems
    solved_records = db.query(DBSubmission.problemId).filter(
        DBSubmission.userId == user_id,
        DBSubmission.verdict == "OK"
    ).all()

    solved_ids = {s[0] for s in solved_records}

    recommendations = []

    # 4. For each weak topic → recommend problems
    for topic_data in weak_topics:

        topic = topic_data["topic"]

        # 🎯 Target difficulty
        target = rating + 100
        min_rating = target - 150
        max_rating = target + 200

        # Fetch candidates
        problems = db.query(DBProblem).filter(
            DBProblem.rating >= min_rating,
            DBProblem.rating <= max_rating
        ).all()

        # Filter + score
        filtered = []

        for prob in problems:

            if prob.problemId in solved_ids:
                continue

            if not prob.tags or topic not in prob.tags:
                continue

            # difficulty closeness score
            diff_score = abs(prob.rating - target)

            filtered.append((diff_score, prob))

        # sort best match first
        filtered.sort(key=lambda x: x[0])

        topic_recommendations = []

        for _, prob in filtered[:4]:

            # build CF link
            match_idx = next(
                (i for i, c in enumerate(prob.problemId) if c.isalpha()),
                len(prob.problemId)
            )

            cf_url = f"https://codeforces.com/problemset/problem/{prob.problemId[:match_idx]}/{prob.problemId[match_idx:]}"

            topic_recommendations.append({
                "problemId": prob.problemId,
                "name": prob.name,
                "rating": prob.rating,
                "tags": prob.tags,
                "link": cf_url
            })

        recommendations.append({
            "topic": topic,
            "priority": topic_data["priority"],
            "gap": topic_data["gap"],
            "problems": topic_recommendations
        })



    # 🔥 Generate AI feedback

    ai_feedback = generate_ai_feedback(
        user_profile={
            "rating": rating
        },
        weak_topics=weak_topics
    )

    return {
        "handle": profile.handle,
        "rating": rating,
        "focus_areas": recommendations,
        "ai_feedback": ai_feedback
    }