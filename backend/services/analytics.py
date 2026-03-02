# backend/services/analytics.py

from sqlalchemy.orm import Session
from models import DBUserSkill, DBBenchmark, DBPlatformProfile

def compare_user_to_benchmark(user_id: str, db: Session):
    # 1. Get user's current rating to find the right bucket
    profile = db.query(DBPlatformProfile).filter(DBPlatformProfile.userId == user_id).first()
    if not profile:
        return {"error": "Platform profile not found"}
    
    # Determine bucket (e.g., 1400-1599)
    rating = profile.currentRating
    bucket = f"{(rating // 200) * 200}-{(rating // 200) * 200 + 199}"
    
    # 2. Fetch User's calculated skills
    user_skills = {s.topic: s.score for s in db.query(DBUserSkill).filter(DBUserSkill.userId == user_id).all()}
    
    # 3. Fetch Benchmark for that bucket
    benchmarks = {b.topic: b for b in db.query(DBBenchmark).filter(DBBenchmark.ratingBucket == bucket).all()}
    
    comparison = []
    for topic, user_score in user_skills.items():
        bench = benchmarks.get(topic)
        if not bench: continue
        
        gap = user_score - bench.avgScore
        status = "Strong" if gap > 20 else "Weak" if gap < -20 else "Average"
        
        comparison.append({
            "topic": topic,
            "user_score": user_score,
            "benchmark_avg": bench.avgScore,
            "gap": round(gap, 2),
            "percentile_status": status
        })
        
    return {
        "handle": profile.handle,
        "current_rating": rating,
        "bucket": bucket,
        "comparison": sorted(comparison, key=lambda x: x['gap']) # Show weaknesses first
    }