# backend/services/sync.py

from .codeforces import fetch_user_submissions
from models import Problem, Submission
from datetime import datetime

async def sync_codeforces_data(handle: str):
    raw_submissions = await fetch_user_submissions(handle)
    
    # We only care about "OK" (Correct) submissions
    solved_problems = [s for s in raw_submissions if s.get("verdict") == "OK"]
    
    # Let's see what topics they are good at
    topic_counts = {}
    
    for sub in solved_problems:
        tags = sub.get("problem", {}).get("tags", [])
        for tag in tags:
            topic_counts[tag] = topic_counts.get(tag, 0) + 1
            
    return {
        "handle": handle,
        "total_solved": len(solved_problems),
        "top_topics": dict(sorted(topic_counts.items(), key=lambda item: item[1], reverse=True)[:5])
    }

def process_cf_submission(raw_data, user_id):
    # 1. Extract Problem info
    problem_data = raw_data.get("problem", {})
    problem = Problem(
        problemId=f"{problem_data.get('contestId')}{problem_data.get('index')}",
        platform="codeforces",
        name=problem_data.get("name"),
        rating=problem_data.get("rating", 0),
        tags=problem_data.get("tags", [])
    )

    # 2. Extract Submission info
    submission = Submission(
        submissionId=raw_data.get("id"),
        userId=user_id,
        problemId=problem.problemId,
        platform="codeforces",
        verdict=raw_data.get("verdict"),
        submittedAt=datetime.fromtimestamp(raw_data.get("creationTimeSeconds"))
    )
    
    return submission, problem