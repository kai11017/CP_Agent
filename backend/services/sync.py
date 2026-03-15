from sqlalchemy.orm import Session
from datetime import datetime
from typing import Tuple

# Import your database models
from models import DBSubmission, DBProblem, DBPlatformProfile
# Import your fetcher
from services.codeforces import fetch_user_submissions, fetch_user_contests
from services.topic_learning import recalculate_user_topic_weights

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

    contestId=raw_data.get("contestId"),

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
        .filter(DBSubmission.userId == user_id)#where user id is userid
        .all()##execute the query and return all resulys
    } ##here sub is like(105,) so sub.submissionid returns 105,,
  ##{} set coz set loookup is O(1) and lsit is O(n)
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
        
    db.commit() # Commit problems first,,

    # 5. Save New Submissions to Database
    for db_sub in new_submissions:
        db.merge(db_sub)
        
    # 6. Update the "lastSyncedAt" timestamp on the user's profile
    profile = db.query(DBPlatformProfile).filter(DBPlatformProfile.handle == handle).first()#return the first matchign row
    if profile:
        profile.lastSyncedAt = datetime.utcnow()

    db.commit() # Final commit

    # 7. Fetch rating history and rebuild topic weights based on recent performance
    try:
        contests_data = await fetch_user_contests(handle)
        recalculate_user_topic_weights(user_id, contests_data, db)
    except Exception as e:
        print(f"Failed to process contests: {str(e)}")

    return {
        "handle": handle,
        "total_fetched": len(raw_submissions),
        "new_submissions_saved": len(new_submissions),
        "unique_problems_updated": len(problems_to_upsert)
    }

## see a problem might be submitted 3 times , so for a problem id we need that only once , so we use this upsert in that batch we see if the problem is 3 times we store only once,, but submission if 3 submission were made we store it 3 times,, 

