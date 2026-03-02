from sqlalchemy.orm import Session
from models import DBUserSkill, DBBenchmark, DBPlatformProfile, DBProblem, DBSubmission
import random

def get_problem_recommendations(user_id: str, db: Session):
    # 1. Get user profile
    profile = db.query(DBPlatformProfile).filter(DBPlatformProfile.userId == user_id).first()
    if not profile: 
        return {"error": "Profile not found"}

    rating = profile.currentRating if profile.currentRating and profile.currentRating > 0 else 1200
    bucket = f"{(rating // 200) * 200}-{(rating // 200) * 200 + 199}"

    # 2. Find the weakest topic (Biggest Gap)
    user_skills = {s.topic: s.score for s in db.query(DBUserSkill).filter(DBUserSkill.userId == user_id).all()}
    benchmarks = {b.topic: b.avgScore for b in db.query(DBBenchmark).filter(DBBenchmark.ratingBucket == bucket).all()}

    weakest_topic = None
    max_gap = -999999

    for topic, bench_score in benchmarks.items():
        u_score = user_skills.get(topic, 0)
        gap = bench_score - u_score
        if gap > max_gap:
            max_gap = gap
            weakest_topic = topic

    if not weakest_topic:
        weakest_topic = "math" # Safe fallback

    # 3. Get problems the user has ALREADY solved
    solved_records = db.query(DBSubmission.problemId).filter(
        DBSubmission.userId == user_id,
        DBSubmission.verdict == "OK"
    ).all()
    solved_ids = {s[0] for s in solved_records}

    # 4. Find 3 problems in the weakest topic, slightly above their rating (+0 to +300)
    target_min = rating
    target_max = rating + 300

    # Fetch candidate problems in the target rating range
    candidate_problems = db.query(DBProblem).filter(
        DBProblem.rating >= target_min,
        DBProblem.rating <= target_max
    ).all()

    recommended = []
    
    # Shuffle so they don't get the exact same 3 problems every time they refresh
    random.shuffle(candidate_problems)

    for prob in candidate_problems:
        if prob.problemId not in solved_ids:
            # Check if the weakest topic is inside the problem's JSON tags
            if prob.tags and weakest_topic in prob.tags:
                
                # Format the Codeforces URL (e.g., 1520A -> problemset/problem/1520/A)
                # We separate the letters from the numbers for the URL structure
                match_idx = next((i for i, c in enumerate(prob.problemId) if c.isalpha()), len(prob.problemId))
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
        "reason": f"Your score in '{weakest_topic}' is {max_gap:.0f} points behind the elite average. Solving these will close the gap.",
        "recommendations": recommended
    }