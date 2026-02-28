from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional

class Problem(BaseModel):
    problemId: str  
    platform: str
    name: str
    rating: Optional[int] = 0
    tags: List[str] = []

class Submission(BaseModel):
    submissionId: int
    userId: UUID
    problemId: str
    platform: str
    verdict: str  # "OK", "WRONG_ANSWER", etc.
    submittedAt: datetime

# this is for identity model
class User(BaseModel):
    userId: UUID
    name: str
    email: str
    createdAt: datetime

class CreateUserRequest(BaseModel):
    name: str
    email: str

# this is form platform wise model
class PlatformProfile(BaseModel):  # users platform profile 
    profileId: UUID
    userId: UUID
    platform: str  # "codeforces", "leetcode", etc.
    handle: str
    currentRating: Optional[int] = 0
    maxRating: Optional[int] = 0
    lastSyncedAt: Optional[datetime] = None

class AddPlatformRequest(BaseModel): # client sends this to add a platform
    platform: str
    handle: str


# section for creating a database schema
# as pydantic is use for data validation and sqlalchemy is use for database schema
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .database import Base

class DBUser(Base):
    __tablename__ = "users"
    userId = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    email = Column(String, unique=True, index=True)
    createdAt = Column(DateTime)

class DBSubmission(Base):
    __tablename__ = "submissions"
    submissionId = Column(Integer, primary_key=True)
    userId = Column(String, index=True)
    problemId = Column(String)
    platform = Column(String)
    verdict = Column(String)
    submittedAt = Column(DateTime)