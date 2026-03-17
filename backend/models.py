from typing import List, Optional
from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional


##furst part-pydantic , the api layer
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
from sqlalchemy import Column, String, Integer, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from database import Base

# table for user database
class DBUser(Base):
    __tablename__ = "users"
    userId = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String)
    email = Column(String, unique=True, index=True)
    createdAt = Column(DateTime)

# table for submission database
class DBSubmission(Base):
    __tablename__ = "submissions"

    submissionId = Column(Integer, primary_key=True)
    userId = Column(String, index=True)
    problemId = Column(String)
    platform = Column(String)

    contestId = Column(Integer, index=True)

    # "CONTESTANT", "OUT_OF_COMPETITION", "PRACTICE", "VIRTUAL"
    participantType = Column(String, default="PRACTICE")

    verdict = Column(String)
    submittedAt = Column(DateTime)
    
    # table for problem database solved by user
class DBProblem(Base):
    __tablename__ = "problems"
    
    # We use a String primary key because Codeforces uses IDs like "1520A"
    problemId = Column(String, primary_key=True, index=True) 
    platform = Column(String) # "codeforces"
    name = Column(String)
    rating = Column(Integer, default=0)
    
    # Storing tags (like "dp", "math") requires a JSON column in Postgres/SQLite
    tags = Column(JSON, default=list) 


# table for platform profiles
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
    

# for storing user skill vector and benchmark dataset
from sqlalchemy import Float

class DBUserSkill(Base):
    """Stores the calculated skill vector for a specific user"""
    __tablename__ = "user_skills"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    userId = Column(String, ForeignKey("users.userId"), index=True)
    topic = Column(String, index=True) # e.g., "math", "dp", "graphs"
    score = Column(Float, default=0.0)
    lastUpdated = Column(DateTime, default=datetime.utcnow)

class DBBenchmark(Base):
    """Stores the standard dataset for each rating bucket"""
    __tablename__ = "benchmarks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String) # "codeforces"
    ratingBucket = Column(String, index=True) # e.g., "1400-1599"
    topic = Column(String) # e.g., "dp"
    
    # Blueprint requirements: avg, p75, p90
    avgScore = Column(Float, default=0.0) 
    p75Score = Column(Float, default=0.0) # 75th percentile (Top 25%)
    p90Score = Column(Float, default=0.0) # 90th percentile (Top 10%)
    
    lastComputed = Column(DateTime, default=datetime.utcnow)


class DBBenchmarkSample(Base):
    """
    Stores individual topic scores used to compute benchmark statistics.
    Each user contributes only once.
    """
    __tablename__ = "benchmark_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)

    userId = Column(String, index=True)  # user contributing this sample
    ratingBucket = Column(String, index=True)

    topic = Column(String, index=True)
    score = Column(Float)

    source = Column(String)  # "seed" or "user"
    createdAt = Column(DateTime, default=datetime.utcnow)


    from sqlalchemy import Column, String, Float, DateTime, Integer, ForeignKey
from datetime import datetime


class DBUserTopicWeight(Base):
    """
    Stores learned topic weights for each user.
    These weights adapt over time based on contest outcomes.
    """

    __tablename__ = "user_topic_weights"

    id = Column(Integer, primary_key=True, autoincrement=True)

    userId = Column(String, ForeignKey("users.userId"), index=True)

    topic = Column(String, index=True)

    weight = Column(Float, default=1.0)

    lastUpdated = Column(DateTime, default=datetime.utcnow)


class DBUserContest(Base):
    """
    Stores per-contest participation data for a user.
    One row per contest the user participated in.
    """
    __tablename__ = "user_contests"
    __table_args__ = (
        UniqueConstraint("userId", "contestId", name="uq_user_contest"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    userId = Column(String, ForeignKey("users.userId"), index=True)
    contestId = Column(Integer, index=True)
    contestName = Column(String)
    ratingBefore = Column(Integer, default=0)
    ratingAfter = Column(Integer, default=0)
    ratingChange = Column(Integer, default=0)
    problemsSolved = Column(Integer, default=0)
    problemsAttempted = Column(Integer, default=0)
    review = Column(String, nullable=True)  # user's post-contest notes (future NLP)
    createdAt = Column(DateTime, default=datetime.utcnow)


class DBUserContestProblem(Base):
    """
    Stores per-problem detail within a contest.
    Tracks solve status, attempts, time-to-solve, and tags.
    """
    __tablename__ = "user_contest_problems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    userContestId = Column(Integer, ForeignKey("user_contests.id"), index=True)
    userId = Column(String, index=True)
    contestId = Column(Integer, index=True)
    problemId = Column(String)
    solved = Column(Integer, default=0)  # 1 = solved, 0 = not solved
    attempts = Column(Integer, default=0)
    timeToSolve = Column(Integer, nullable=True)  # seconds from contest start to first AC
    problemRating = Column(Integer, default=0)
    tags = Column(JSON, default=list)