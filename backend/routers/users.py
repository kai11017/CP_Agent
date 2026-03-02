from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime

# Import Database setup
from database import get_db

# Import Models (Make sure DBPlatformProfile is in models.py, NOT here!)
from models import DBUser, DBPlatformProfile, CreateUserRequest, AddPlatformRequest

# Import Services
from services.codeforces import fetch_user_info, fetch_user_submissions
from services.sync import sync_codeforces_data
from services.compute_skill import compute_user_vector
from services.analytics import compare_user_to_benchmark
from services.gap_analysis import get_performance_report
from services.recommendations import get_problem_recommendations

router = APIRouter()


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


# 4) run the sync engine
@router.post("/users/{user_id}/sync")
async def trigger_sync(user_id: str, handle: str, db: Session = Depends(get_db)):
    """
    Fetches raw data, checks for duplicates, and saves everything to PostgreSQL/SQLite.
    """
    try:
        result = await sync_codeforces_data(handle, user_id, db)
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


# 6) get user performance report
@router.get("/users/{user_id}/report")
def get_user_report(user_id: str, db: Session = Depends(get_db)):
    return get_performance_report(user_id, db)

# 7) get problem recommendations
@router.get("/users/{user_id}/recommendations")
def get_recommendations(user_id: str, db: Session = Depends(get_db)):
    """
    Returns 3 tailored Codeforces problems based on the user's biggest skill gap.
    """
    return get_problem_recommendations(user_id, db)
