from sqlalchemy.orm import Session
from models import DBUserSkill, DBBenchmark, DBPlatformProfile, DBSubmission, DBProblem

def get_performance_report(user_id: str, db: Session):
    # 1. Get the user's handle for the report
    profile = db.query(DBPlatformProfile).filter(DBPlatformProfile.userId == user_id).first()
    if not profile:
        return {"error": "User profile not found. Have you synced your handle yet?"}

    # 2. Get User's Skills
    user_skills = db.query(DBUserSkill).filter(DBUserSkill.userId == user_id).all()
    user_map = {s.topic: s.score for s in user_skills}

    # 3. Get the "Elite" Benchmark (The one we just seeded: 2000-4000 bucket)
    benchmarks = db.query(DBBenchmark).filter(DBBenchmark.ratingBucket == "2000-4000").all()
    
    # 4. Fetch last contest struggles
    last_contest_subs = (
        db.query(DBSubmission, DBProblem)
        .join(DBProblem, DBSubmission.problemId == DBProblem.problemId)
        .filter(DBSubmission.userId == user_id)
        .filter(DBSubmission.contestId.isnot(None))
        .order_by(DBSubmission.submittedAt.desc())
        .all()
    )
    
    immediate_struggles = set()
    if last_contest_subs:
        last_contest_id = last_contest_subs[0][0].contestId
        
        # Find struggles in that contest
        for sub, prob in last_contest_subs:
            if sub.contestId == last_contest_id and sub.verdict != "OK":
                tags = prob.tags if prob.tags else ["general"]
                for tag in tags:
                    immediate_struggles.add(tag)
                    
        # Remove topics they actually solved in the same contest
        for sub, prob in last_contest_subs:
            if sub.contestId == last_contest_id and sub.verdict == "OK":
                tags = prob.tags if prob.tags else []
                for tag in tags:
                    if tag in immediate_struggles:
                        immediate_struggles.remove(tag)
    
    report = []
    for bench in benchmarks:
        user_score = user_map.get(bench.topic, 0)
        # Calculate the % of the elite level the user has reached
        coverage_pct = (user_score / bench.avgScore * 100) if bench.avgScore > 0 else 0
        
        report.append({
            "topic": bench.topic,
            "your_score": round(user_score, 2),
            "elite_avg": bench.avgScore, # Target required weightage
            "gap_to_elite": round(bench.avgScore - user_score, 2),
            "mastery_percentage": f"{round(coverage_pct, 1)}%",
            "is_immediate_struggle": bench.topic in immediate_struggles
        })

    # Sort by lowest to highest skill so the user can see their weak points first
    report.sort(key=lambda x: x['your_score'])

    return {
        "handle": profile.handle,
        "rating": profile.currentRating,
        "comparison_group": "Grandmasters/Masters",
        "last_contest_struggles": list(immediate_struggles),
        "analysis": report
    }