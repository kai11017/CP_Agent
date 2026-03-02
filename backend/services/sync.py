from sqlalchemy.orm import Session
from datetime import datetime
from typing import Tuple

# Import your database models
from models import DBSubmission, DBProblem, DBPlatformProfile
# Import your fetcher
from services.codeforces import fetch_user_submissions


def process_cf_submission(raw_data: dict, user_id: str) -> Tuple[DBSubmission, DBProblem]:
    """
    Helper function to convert raw Codeforces JSON into SQLAlchemy Objects.
    """
    problem_data = raw_data.get("problem", {})
    
    # Construct a unique Problem ID (e.g., "1520A")
    contest_id = problem_data.get('contestId', '')
    index = problem_data.get('index', '')
    p_id = f"{contest_id}{index}"

    # 1. Create DBProblem object
    db_problem = DBProblem(
        problemId=p_id,
        platform="codeforces",
        name=problem_data.get("name", "Unknown"),
        rating=problem_data.get("rating", 0),
        tags=problem_data.get("tags", [])
    )

    # 2. Create DBSubmission object
    db_submission = DBSubmission(
        submissionId=raw_data.get("id"),
        userId=user_id,
        problemId=p_id,
        platform="codeforces",
        verdict=raw_data.get("verdict", "UNKNOWN"),
        submittedAt=datetime.fromtimestamp(raw_data.get("creationTimeSeconds"))
    )
    
    return db_submission, db_problem


async def sync_codeforces_data(handle: str, user_id: str, db: Session) -> dict:
    """
    The main engine: Fetches, filters duplicates, and saves to PostgreSQL.
    """
    # 1. Fetch ALL raw submissions from Codeforces API
    raw_submissions = await fetch_user_submissions(handle)
    
    # 2. INCREMENTAL UPDATE LOGIC (Rule 2 from your blueprint)
    # Get all submission IDs we ALREADY have in the database for this user
    existing_sub_ids = {
        sub.submissionId for sub in db.query(DBSubmission.submissionId)
        .filter(DBSubmission.userId == user_id)
        .all()
    }

    new_submissions = []
    problems_to_upsert = {}

    # 3. Process the raw data
    for raw_data in raw_submissions:
        sub_id = raw_data.get("id")
        
        # If we already have this submission, skip it!
        if sub_id in existing_sub_ids:
            continue
            
        # Convert JSON to DB objects
        db_sub, db_prob = process_cf_submission(raw_data, user_id)
        
        new_submissions.append(db_sub)
        
        # We use a dictionary for problems so we don't try to insert the 
        # same problem twice in a single batch (e.g., user submitted to 1520A three times)
        if db_prob.problemId not in problems_to_upsert:
            problems_to_upsert[db_prob.problemId] = db_prob

    # 4. Save Problems to Database
    for prob in problems_to_upsert.values():
        # db.merge() is a SQLAlchemy trick. 
        # If the problem exists, it updates it. If not, it inserts it.
        db.merge(prob)
        
    db.commit() # Commit problems first

    # 5. Save New Submissions to Database
    for db_sub in new_submissions:
        db.merge(db_sub)
        
    # 6. Update the "lastSyncedAt" timestamp on the user's profile
    profile = db.query(DBPlatformProfile).filter(DBPlatformProfile.handle == handle).first()
    if profile:
        profile.lastSyncedAt = datetime.utcnow()

    db.commit() # Final commit

    return {
        "handle": handle,
        "total_fetched": len(raw_submissions),
        "new_submissions_saved": len(new_submissions),
        "unique_problems_updated": len(problems_to_upsert)
    }