from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from typing import Tuple
from collections import defaultdict

# Import your database models
from models import DBSubmission, DBProblem, DBPlatformProfile, DBUserContest, DBUserContestProblem
# Import your fetcher
from services.codeforces import fetch_user_submissions, fetch_user_rating_changes, fetch_contest_list


def process_cf_submission(raw_data: dict, user_id: str) -> Tuple[DBSubmission, DBProblem]:
    """
    Helper function to convert raw Codeforces JSON into SQLAlchemy Objects.
    Now also extracts participantType from the author field.
    """
    problem_data = raw_data.get("problem", {})
    
    # Construct a unique Problem ID (e.g., "1520A")
    contest_id = problem_data.get('contestId', '')
    index = problem_data.get('index', '')
    p_id = f"{contest_id}{index}"

    # Extract participantType from author.Party
    author = raw_data.get("author", {})
    participant_type = author.get("participantType", "PRACTICE")

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
        participantType=participant_type,
        verdict=raw_data.get("verdict", "UNKNOWN"),
        submittedAt=datetime.fromtimestamp(raw_data.get("creationTimeSeconds"))
    )
    
    return db_submission, db_problem


async def sync_codeforces_data(handle: str, user_id: str, db: Session) -> dict:
    """
    The main engine: Fetches, filters duplicates, and saves to DB.
    UNCHANGED behavior — only adds participantType to each submission.
    """
    # 1. Fetch ALL raw submissions from Codeforces API
    raw_submissions = await fetch_user_submissions(handle)
    
    # 2. INCREMENTAL UPDATE LOGIC
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
        
        # Deduplicate problems in the same batch
        if db_prob.problemId not in problems_to_upsert:
            problems_to_upsert[db_prob.problemId] = db_prob

    # 4. Save Problems to Database (merge needed — upsert semantics)
    for prob in problems_to_upsert.values():
        db.merge(prob)

    # 5. Save New Submissions to Database
    # Duplicates already filtered above, so add_all() is safe and faster than merge()
    for sub in new_submissions:
        db.merge(sub)
    # 6. Update the "lastSyncedAt" timestamp on the user's profile
    profile = db.query(DBPlatformProfile).filter(DBPlatformProfile.handle == handle).first()
    if profile:
        profile.lastSyncedAt = datetime.utcnow()

    # Single commit for the entire function
    db.commit()

    return {
        "handle": handle,
        "total_fetched": len(raw_submissions),
        "new_submissions_saved": len(new_submissions),
        "unique_problems_updated": len(problems_to_upsert)
    }


async def sync_contest_history(handle: str, user_id: str, db: Session) -> dict:
    """
    Syncs contest participation data.
    Called AFTER sync_codeforces_data(). Populates user_contests and
    user_contest_problems tables using rating changes + stored submissions.
    """
    # 1. Fetch rating change history
    print(f"[DEBUG] Fetching rating changes for {handle}...", flush=True)
    rating_changes = await fetch_user_rating_changes(handle)
    print(f"[DEBUG] Got {len(rating_changes)} rating changes", flush=True)
    if not rating_changes:
        print(f"[DEBUG] No rating changes found! Returning early.", flush=True)
        return {"contests_synced": 0, "debug": "no_rating_changes_found"}

    # 1b. Fetch official contest start times (cached, refreshed every 24h)
    raw_contest_start_map = await fetch_contest_list()
    contest_start_map = {
        cid: datetime.utcfromtimestamp(ts)
        for cid, ts in raw_contest_start_map.items()
    }

    # 2. Get already-synced contest IDs for this user
    existing_contest_ids = {
        c.contestId for c in db.query(DBUserContest.contestId)
        .filter(DBUserContest.userId == user_id)
        .all()
    }

    # 2b. Build filtered list of unsynced contests — loop directly, no re-checking
    unsynced_contests = [
        rc for rc in rating_changes
        if rc["contestId"] not in existing_contest_ids
    ]
    if not unsynced_contests:
        print(f"[DEBUG] All contests already synced for {handle}.", flush=True)
        return {"contests_synced": 0, "total_contests": len(rating_changes)}

    unsynced_contest_ids = [rc["contestId"] for rc in unsynced_contests]

    # 3. Batch-fetch ONLY submissions for unsynced contests (O(1) query, filtered)
    all_contest_subs = (
        db.query(DBSubmission, DBProblem)
        .join(DBProblem, DBSubmission.problemId == DBProblem.problemId)
        .filter(DBSubmission.userId == user_id)
        .filter(DBSubmission.contestId.in_(unsynced_contest_ids))
        .filter(DBSubmission.participantType.in_(["CONTESTANT", "OUT_OF_COMPETITION"]))
        .all()
    )

    # Group submissions by contestId in memory
    subs_by_contest = defaultdict(list)
    for sub, prob in all_contest_subs:
        subs_by_contest[sub.contestId].append((sub, prob))

    # Hoist timestamp outside loop — reuse for all rows
    now = datetime.utcnow()

    new_contests = 0
    contests_without_subs = 0

    for rc in unsynced_contests:
        contest_id = rc["contestId"]

        # 4. Get submissions for this contest from the pre-fetched map
        contest_subs = subs_by_contest.get(contest_id, [])
        had_submissions = len(contest_subs) > 0

        if not had_submissions:
            contests_without_subs += 1

        # 5. Aggregate per-problem stats (order-independent — no .order_by() needed)
        problem_stats = defaultdict(lambda: {
            "attempts": 0,
            "solved": False,
            "first_ac_time": None,
            "first_sub_time": None,
            "prob": None
        })

        for sub, prob in contest_subs:
            pid = prob.problemId
            stats = problem_stats[pid]
            stats["prob"] = prob
            stats["attempts"] += 1

            # Explicit min — correct regardless of query order
            if stats["first_sub_time"] is None or sub.submittedAt < stats["first_sub_time"]:
                stats["first_sub_time"] = sub.submittedAt

            if sub.verdict == "OK":
                if stats["first_ac_time"] is None or sub.submittedAt < stats["first_ac_time"]:
                    stats["solved"] = True
                    stats["first_ac_time"] = sub.submittedAt

        problems_solved = sum(1 for s in problem_stats.values() if s["solved"])
        problems_attempted = len(problem_stats)

        # 6. Create DBUserContest row (always — even with 0 submissions, rating data is valuable)
        user_contest = DBUserContest(
            userId=user_id,
            contestId=contest_id,
            contestName=rc["contestName"],
            ratingBefore=rc["oldRating"],
            ratingAfter=rc["newRating"],
            ratingChange=rc["ratingChange"],
            problemsSolved=problems_solved,
            problemsAttempted=problems_attempted,
            createdAt=now
        )
        db.add(user_contest)
        db.flush()  # get the auto-generated id

        # 7. Create DBUserContestProblem rows
        contest_start = contest_start_map.get(contest_id)
        if contest_start is None:
            print(f"[WARNING] No start time found for contest {contest_id} — timeToSolve will be None", flush=True)

        for pid, stats in problem_stats.items():
            prob = stats["prob"]
            time_to_solve = None

            if stats["solved"] and stats["first_ac_time"] and contest_start:
                delta = (stats["first_ac_time"] - contest_start).total_seconds()
                time_to_solve = int(delta) if delta >= 0 else None

            contest_problem = DBUserContestProblem(
                userContestId=user_contest.id,
                userId=user_id,
                contestId=contest_id,
                problemId=pid,
                solved=1 if stats["solved"] else 0,
                attempts=stats["attempts"],
                timeToSolve=time_to_solve,
                problemRating=prob.rating if prob and prob.rating else 0,
                tags=prob.tags if prob and prob.tags else []
            )
            db.add(contest_problem)

        new_contests += 1

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        print(f"[WARNING] IntegrityError during contest sync for {handle} — likely concurrent duplicate. Rolled back.", flush=True)
        return {
            "handle": handle,
            "contests_synced": 0,
            "error": "duplicate_contest_entry",
            "total_contests": len(rating_changes)
        }

    return {
        "handle": handle,
        "contests_synced": new_contests,
        "contests_without_submissions": contests_without_subs,
        "total_contests": len(rating_changes)
    }

