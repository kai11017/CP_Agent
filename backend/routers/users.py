from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from services.topic_weights import initialize_user_topic_weights
# Import Database setup
from database import get_db

# Import Models
from models import DBUser, DBPlatformProfile, DBUserContest, DBUserContestProblem, CreateUserRequest, AddPlatformRequest

# Import Services
from services.codeforces import fetch_user_info, fetch_user_submissions
from services.sync import sync_codeforces_data, sync_contest_history
from services.compute_skill import compute_user_vector, compute_contest_skill_vector
from services.analytics import compare_user_to_benchmark
from services.gap_analysis import get_performance_report, get_topic_weakness_report
from services.recommendations import get_problem_recommendations
from services.topic_learning import update_topic_weights_after_contest

router = APIRouter()


# ————————————————————————————————————
# EXISTING ENDPOINTS (unchanged behavior)
# ————————————————————————————————————

# 1) creation of user
@router.post("/users")
def create_user(payload: CreateUserRequest, db: Session = Depends(get_db)):
    db_user = DBUser(
        name=payload.name,
        email=payload.email,
        createdAt=datetime.utcnow()
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# 2) linking platform handle of user
@router.post("/users/{user_id}/platform")
async def link_platform(user_id: str, payload: AddPlatformRequest, db: Session = Depends(get_db)):
    try:
        if payload.platform.lower() == "codeforces":
            # Fetch live data from Codeforces to verify the handle
            cf_data = await fetch_user_info(payload.handle)
            
            # Create the Database Record
            new_profile = DBPlatformProfile(
                userId=user_id,
                platform="codeforces",
                handle=payload.handle,
                currentRating=cf_data.get("rating", 0),
                maxRating=cf_data.get("maxRating", 0),
                lastSyncedAt=datetime.utcnow()
            )
            
            db.add(new_profile)
            db.commit()
            db.refresh(new_profile)
            
            return {"status": "Linked successfully", "profile": new_profile}
        
        else:
            raise HTTPException(status_code=400, detail="Platform not supported")
            
    except Exception as e:
        db.rollback() 
        raise HTTPException(status_code=404, detail=f"Codeforces verification failed: {str(e)}")


# 3) preview raw submissions for testing
@router.get("/users/{handle}/submissions-preview")
async def get_external_submissions(handle: str):
    """
    Directly fetches submissions from Codeforces for a specific handle.
    Does NOT save to database. Use this to verify API service is working.
    """
    data = await fetch_user_submissions(handle)
    return {"handle": handle, "count": len(data), "latest": data[:5]}


# 4) run the sync engine — NOW ALSO SYNCS CONTEST HISTORY
@router.post("/users/{user_id}/sync")
async def trigger_sync(user_id: str, handle: str, db: Session = Depends(get_db)):
    """
    Fetches raw data, checks for duplicates, saves submissions,
    then syncs contest history and updates topic weights.
    """
    try:
        # Step 1: Original sync (unchanged)
        result = await sync_codeforces_data(handle, user_id, db)
        initialize_user_topic_weights(user_id, db)

        # Step 2: NEW — sync contest history (additive)
        contest_result = await sync_contest_history(handle, user_id, db)

        # Step 3: NEW — update topic weights for each new contest
        new_contests = (
            db.query(DBUserContest)
            .filter(DBUserContest.userId == user_id)
            .all()
        )
        for contest in new_contests:
            if contest.ratingChange != 0:
                update_topic_weights_after_contest(user_id, contest.contestId, contest.ratingChange, db)

        result["contest_sync"] = contest_result
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


# 5) get user skill vector
@router.get("/users/{user_id}/skill")
def get_user_skill(user_id: str, db: Session = Depends(get_db)):
    """
    Calculates and returns the user's current skill vector based on saved DB data.
    """
    try:
        skill_data = compute_user_vector(user_id, db)
        return skill_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute skill: {str(e)}")


# 6) evaluate user
@router.get("/users/{user_id}/evaluate")
def evaluate_user(user_id: str, db: Session = Depends(get_db)):
    """
    The 'Truth' endpoint. Compares user to their peers and returns insights.
    """
    return compare_user_to_benchmark(user_id, db)


# 7) get user performance report
@router.get("/users/{user_id}/report")
def get_user_report(user_id: str, db: Session = Depends(get_db)):
    return get_performance_report(user_id, db)

# 8) get problem recommendations
@router.get("/users/{user_id}/recommendations")
def get_recommendations(user_id: str, db: Session = Depends(get_db)):
    """
    Returns 3 tailored Codeforces problems based on the user's biggest skill gap.
    """
    return get_problem_recommendations(user_id, db)


# ————————————————————————————————————
# NEW ENDPOINTS (contest-aware features)
# ————————————————————————————————————

# 9) get contest skill vector (under-pressure performance)
@router.get("/users/{user_id}/contest-skill")
def get_contest_skill(user_id: str, db: Session = Depends(get_db)):
    """
    Returns skill vector computed ONLY from contest submissions.
    Represents performance under contest pressure.
    """
    try:
        return compute_contest_skill_vector(user_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute contest skill: {str(e)}")


# 10) list all contests
@router.get("/users/{user_id}/contests")
def get_user_contests(user_id: str, db: Session = Depends(get_db)):
    """
    Returns all contests the user participated in, sorted by most recent first.
    """
    contests = (
        db.query(DBUserContest)
        .filter(DBUserContest.userId == user_id)
        .order_by(DBUserContest.contestId.desc())
        .all()
    )

    return {
        "user_id": user_id,
        "total_contests": len(contests),
        "contests": [
            {
                "contestId": c.contestId,
                "name": c.contestName,
                "ratingBefore": c.ratingBefore,
                "ratingAfter": c.ratingAfter,
                "ratingChange": c.ratingChange,
                "problemsSolved": c.problemsSolved,
                "problemsAttempted": c.problemsAttempted,
                "review": c.review
            }
            for c in contests
        ]
    }


# 11) get contest detail with per-problem breakdown
@router.get("/users/{user_id}/contests/{contest_id}")
def get_contest_detail(user_id: str, contest_id: int, db: Session = Depends(get_db)):
    """
    Returns detailed breakdown of a single contest with per-problem stats.
    """
    contest = (
        db.query(DBUserContest)
        .filter(DBUserContest.userId == user_id)
        .filter(DBUserContest.contestId == contest_id)
        .first()
    )

    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    problems = (
        db.query(DBUserContestProblem)
        .filter(DBUserContestProblem.userContestId == contest.id)
        .all()
    )

    return {
        "contestId": contest.contestId,
        "name": contest.contestName,
        "ratingBefore": contest.ratingBefore,
        "ratingAfter": contest.ratingAfter,
        "ratingChange": contest.ratingChange,
        "problemsSolved": contest.problemsSolved,
        "problemsAttempted": contest.problemsAttempted,
        "review": contest.review,
        "problems": [
            {
                "problemId": p.problemId,
                "solved": bool(p.solved),
                "attempts": p.attempts,
                "timeToSolve": p.timeToSolve,
                "rating": p.problemRating,
                "tags": p.tags
            }
            for p in problems
        ]
    }


class ReviewRequest(BaseModel):
    review: str

# 12) save post-contest review
@router.put("/users/{user_id}/contests/{contest_id}/review")
def save_contest_review(user_id: str, contest_id: int, payload: ReviewRequest, db: Session = Depends(get_db)):
    """
    Save a user's post-contest review/notes (for future NLP processing).
    """
    contest = (
        db.query(DBUserContest)
        .filter(DBUserContest.userId == user_id)
        .filter(DBUserContest.contestId == contest_id)
        .first()
    )

    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    contest.review = payload.review
    db.commit()

    return {"status": "Review saved", "contestId": contest_id}


# 13) get topic weaknesses sorted
@router.get("/users/{user_id}/weaknesses")
def get_weaknesses(user_id: str, db: Session = Depends(get_db)):
    """
    Returns topics sorted by weakness (worst first).
    Combines benchmark gaps, contest solve rates, difficulty ceilings,
    and learned topic weights into a priority score.
    """
    return get_topic_weakness_report(user_id, db)
