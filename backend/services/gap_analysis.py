from sqlalchemy.orm import Session
from models import DBUserSkill, DBBenchmark, DBPlatformProfile

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
    
    report = []
    for bench in benchmarks:
        user_score = user_map.get(bench.topic, 0)
        # Calculate the % of the elite level the user has reached
        # If Tourist has 5000 and you have 500, you are at 10% of elite capacity.
        coverage_pct = (user_score / bench.avgScore * 100) if bench.avgScore > 0 else 0
        
        report.append({
            "topic": bench.topic,
            "your_score": round(user_score, 2),
            "elite_avg": bench.avgScore,
            "gap_to_elite": round(bench.avgScore - user_score, 2),
            "mastery_percentage": f"{round(coverage_pct, 1)}%"
        })

    # Sort by the biggest gaps first (where you need most work)
    report.sort(key=lambda x: x['gap_to_elite'], reverse=True)

    return {
        "handle": profile.handle,
        "rating": profile.currentRating,
        "comparison_group": "Grandmasters/Masters",
        "analysis": report[:10] # Top 10 topics to focus on
    }