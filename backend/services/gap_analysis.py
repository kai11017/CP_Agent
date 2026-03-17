from sqlalchemy.orm import Session
from models import DBUserSkill, DBBenchmark, DBPlatformProfile, DBUserContestProblem, DBUserTopicWeight
from collections import defaultdict

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


def get_topic_weakness_report(user_id: str, db: Session):
    """
    Returns topics sorted by weakness (worst first) using contest data.
    Combines: skill scores, benchmark gaps, contest solve rates,
    difficulty ceilings, and learned topic weights.
    """
    profile = db.query(DBPlatformProfile).filter(DBPlatformProfile.userId == user_id).first()
    if not profile:
        return {"error": "Profile not found"}

    # 1. Get user skills
    user_skills = {s.topic: s.score for s in db.query(DBUserSkill).filter(DBUserSkill.userId == user_id).all()}

    # 2. Get benchmarks
    rating = profile.currentRating if profile.currentRating else 1200
    bucket = f"{(rating // 200) * 200}-{(rating // 200) * 200 + 199}"
    benchmarks = {b.topic: b.avgScore for b in db.query(DBBenchmark).filter(DBBenchmark.ratingBucket == bucket).all()}

    # 3. Get topic weights
    topic_weights = {w.topic: w.weight for w in db.query(DBUserTopicWeight).filter(DBUserTopicWeight.userId == user_id).all()}

    # 4. Compute contest performance per topic
    contest_problems = db.query(DBUserContestProblem).filter(DBUserContestProblem.userId == user_id).all()

    topic_contest_stats = defaultdict(lambda: {"solved": 0, "attempted": 0, "max_rating_solved": 0})

    for cp in contest_problems:
        tags = cp.tags if cp.tags else ["general"]
        for tag in tags:
            stats = topic_contest_stats[tag]
            stats["attempted"] += 1
            if cp.solved:
                stats["solved"] += 1
                if cp.problemRating and cp.problemRating > stats["max_rating_solved"]:
                    stats["max_rating_solved"] = cp.problemRating

    # 5. Build weakness report
    all_topics = set(list(user_skills.keys()) + list(benchmarks.keys()) + list(topic_contest_stats.keys()))

    report = []
    for topic in all_topics:
        user_score = user_skills.get(topic, 0)
        bench_score = benchmarks.get(topic, 0)
        weight = topic_weights.get(topic, 1.0)
        contest_stats = topic_contest_stats.get(topic, {"solved": 0, "attempted": 0, "max_rating_solved": 0})

        gap = bench_score - user_score
        solve_rate = (contest_stats["solved"] / contest_stats["attempted"] * 100) if contest_stats["attempted"] > 0 else 0

        # Priority score: higher = weaker (needs more practice)
        priority = gap * weight

        report.append({
            "topic": topic,
            "your_score": round(user_score, 2),
            "benchmark_avg": round(bench_score, 2),
            "gap": round(gap, 2),
            "weight": round(weight, 2),
            "priority": round(priority, 2),
            "contest_solve_rate": f"{round(solve_rate, 1)}%",
            "contest_attempted": contest_stats["attempted"],
            "difficulty_ceiling": contest_stats["max_rating_solved"]
        })

    # Sort by priority (highest priority = weakest topic first)
    report.sort(key=lambda x: x['priority'], reverse=True)

    return {
        "handle": profile.handle,
        "rating": profile.currentRating,
        "bucket": bucket,
        "weaknesses": report
    }