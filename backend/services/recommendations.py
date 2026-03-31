# backend/services/recommendation.py

from sqlalchemy.orm import Session
from models import DBProblem, DBSubmission, DBPlatformProfile
from services.gap_analysis import get_topic_weakness_report
from services.ai_coach import generate_ai_feedback

KNOWLEDGE_GRAPH = {
    "dp": ["greedy", "math"],
    "graphs": ["dfs and similar", "data structures"],
    "trees": ["dfs and similar"],
    "dfs and similar": ["implementation"],
    "number theory": ["math"],
    "combinatorics": ["math"],
    "geometry": ["math"],
    "binary search": ["sortings"],
    "two pointers": ["sortings"],
    "bitmasks": ["math", "implementation"],
    "shortest paths": ["graphs"],
    "dsu": ["graphs", "trees"],
    "divide and conquer": ["binary search"],
    "graph matchings": ["graphs"],
    "string suffix structures": ["strings"],
    "hashing": ["strings"],
    "matrices": ["math"],
    "fft": ["math"],
    "meet-in-the-middle": ["binary search", "brute force"],
    "ternary search": ["binary search"]
}

def get_root_weak_topic(topic, weakness_map, visited=None):
    if visited is None:
        visited = set()
        
    if topic in visited:
        return topic # Prevent infinite loops
    visited.add(topic)
    
    prereqs = KNOWLEDGE_GRAPH.get(topic, [])
    
    # Check if user lacks a strong hold on any prerequisite
    for prereq in prereqs:
        prereq_data = weakness_map.get(prereq)
        if prereq_data:
            # If gap > 0, score < average, so NO strong hold
            if prereq_data["gap"] > 0:
                # Recursively resolve this weaker prerequisite
                return get_root_weak_topic(prereq, weakness_map, visited)
                
    # Topics with all strong hold prerequisites (or no prerequisites) are returned
    return topic

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

    # Create weakness_map for O(1) lookups
    weakness_map = {w["topic"]: w for w in weakness_data["weaknesses"]}

    # 🔥 Resolve foundational topics using the Knowledge Graph
    resolved_topics = []
    seen = set()

    # Traverse using the original prioritized weakness list
    for topic_data in weakness_data["weaknesses"]:
        if topic_data["gap"] <= 0:
            continue # Skip topics where gap is already <= 0 (strong hold)

        root_topic = get_root_weak_topic(topic_data["topic"], weakness_map)
        
        # Don't add duplicate foundational topics
        if root_topic not in seen:
            seen.add(root_topic)
            # Find the actual data for this foundational topic
            root_data = weakness_map.get(root_topic)
            if root_data:
                resolved_topics.append(root_data)
                
        # Stop once we have 5 unique topics
        if len(resolved_topics) == 5:
            break

    # If the user has a strong hold on almost everything, fallback to normal weaknesses
    if not resolved_topics:
        resolved_topics = weakness_data["weaknesses"][:5]

    weak_topics = resolved_topics

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