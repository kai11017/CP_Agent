from fastapi import APIRouter, HTTPException
from uuid import uuid4
from datetime import datetime
from typing import List

# importing fetchers from services and models module
from services.codeforces import fetch_user_info, fetch_user_submissions
from models import User, CreateUserRequest, PlatformProfile, AddPlatformRequest
from services.sync import sync_codeforces_data

router = APIRouter()

# replacing user db local with real database logic
from sqlalchemy.orm import Session
from fastapi import Depends
from database import get_db
from models import DBUser, DBPlatformProfile  # The SQLAlchemy version

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

# replacing platform db local with real database logic
class DBPlatformProfile(Base):
    __tablename__ = "platform_profiles"
    
    profileId = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    # Links this profile to a specific user
    userId = Column(String, ForeignKey("users.userId"), index=True)
    platform = Column(String)  # "codeforces"
    handle = Column(String, index=True)
    currentRating = Column(Integer, default=0)
    maxRating = Column(Integer, default=0)
    lastSyncedAt = Column(DateTime, default=datetime.utcnow)


@router.post("/users/{user_id}/platform")
async def link_platform(user_id: str, payload: AddPlatformRequest, db: Session = Depends(get_db)):
    try:
        if payload.platform.lower() == "codeforces":
            # 1. Fetch live data from Codeforces to verify the handle
            cf_data = await fetch_user_info(payload.handle)
            
            # 2. Create the Database Record
            new_profile = DBPlatformProfile(
                userId=user_id,
                platform="codeforces",
                handle=payload.handle,
                currentRating=cf_data.get("rating", 0),
                maxRating=cf_data.get("maxRating", 0),
                lastSyncedAt=datetime.utcnow()
            )
            
            # 3. Save to PostgreSQL (or SQLite for now)
            db.add(new_profile)
            db.commit()
            db.refresh(new_profile)
            
            return {"status": "Linked successfully", "profile": new_profile}
        
        else:
            raise HTTPException(status_code=400, detail="Platform not supported")
            
    except Exception as e:
        db.rollback() # Undo database changes if API fetch fails
        raise HTTPException(status_code=404, detail=f"Codeforces verification failed: {str(e)}")


@router.get("/users/{user_id}/submissions")
async def get_external_submissions(handle: str):
    """
    Directly fetches submissions from Codeforces for a specific handle.
    Use this to verify your API service is working.
    """
    data = await fetch_user_submissions(handle)
    return {"handle": handle, "count": len(data), "latest": data[:5]}


@router.get("/users/{handle}/sync")
async def sync_user(handle: str):
    summary = await sync_codeforces_data(handle)
    return summary