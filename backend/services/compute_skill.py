import math
from collections import defaultdict
from datetime import datetime
from sqlalchemy.orm import Session
from models import DBSubmission, DBProblem, DBUserSkill


def calculate_problem_weight(rating: int) -> float:
    if not rating or rating < 800:
        rating = 800
    return ((rating / 1000.0) ** 2) * 20


def calculate_recency_weight(submitted_at):
    months = (datetime.utcnow() - submitted_at).days / 30
    return math.exp(-0.05 * months)


def calculate_attempt_penalty(attempts: int) -> float:
    if attempts <= 1:
        return 1.0
    elif attempts == 2:
        return 0.9
    elif attempts == 3:
        return 0.8
    elif attempts == 4:
        return 0.7
    else:
        return 0.6


def calculate_diminishing_returns(scores: list) -> float:
    scores.sort(reverse=True)
    total = 0
    for i, score in enumerate(scores):
        total += score * (0.9 ** i)
    return round(total, 2)


# -----------------------------
# PURE COMPUTATION FUNCTION
# -----------------------------
def calculate_skill_vector(user_id: str, db: Session):

    submissions = (
        db.query(DBSubmission, DBProblem)
        .join(DBProblem, DBSubmission.problemId == DBProblem.problemId)
        .filter(DBSubmission.userId == user_id)
        .order_by(DBSubmission.submittedAt)
        .all()
    )

    problem_attempts = defaultdict(list)

    for sub, prob in submissions:
        problem_attempts[prob.problemId].append((sub, prob))

    topic_scores = defaultdict(list)

    solved_problem_count = 0

    for problem_id, attempts_list in problem_attempts.items():

        attempts = 0
        first_ac_found = False
        attempts_until_ac = None
        latest_ac_time = None
        prob = None

        for sub, p in attempts_list:
            attempts += 1
            prob = p

            if sub.verdict == "OK":

                if not first_ac_found:
                    attempts_until_ac = attempts
                    first_ac_found = True

                latest_ac_time = sub.submittedAt

        if not first_ac_found:
            continue

        solved_problem_count += 1

        difficulty_weight = calculate_problem_weight(prob.rating)
        recency_weight = calculate_recency_weight(latest_ac_time)
        attempt_penalty = calculate_attempt_penalty(attempts_until_ac)

        problem_score = difficulty_weight * recency_weight * attempt_penalty

        tags = prob.tags if prob.tags else ["general"]

        score_per_tag = problem_score / len(tags)

        for tag in tags:
            topic_scores[tag].append(score_per_tag)

    final_skills = {}

    for tag, scores in topic_scores.items():
        final_skills[tag] = calculate_diminishing_returns(scores)

    sorted_skills = dict(sorted(final_skills.items(), key=lambda x: x[1], reverse=True))

    return sorted_skills, solved_problem_count


# -----------------------------
# REAL USER WRAPPER
# -----------------------------
def compute_user_vector(user_id: str, db: Session):

    skill_vector, solved_problem_count = calculate_skill_vector(user_id, db)

    db.query(DBUserSkill).filter(DBUserSkill.userId == user_id).delete()

    db_skills = []

    for tag, score in skill_vector.items():
        db_skills.append(
            DBUserSkill(
                userId=user_id,
                topic=tag,
                score=score,
                lastUpdated=datetime.utcnow()
            )
        )

    if db_skills:
        db.add_all(db_skills)
        db.commit()

    return {
        "user_id": user_id,
        "total_unique_solved": solved_problem_count,
        "skill_vector": skill_vector
    }


# -----------------------------
# CONTEST-ONLY SKILL VECTOR
# -----------------------------
def compute_contest_skill_vector(user_id: str, db: Session):
    """
    Same algorithm as calculate_skill_vector but ONLY for contest submissions.
    Filters to participantType IN ('CONTESTANT', 'OUT_OF_COMPETITION').
    Returns skill vector representing performance under contest pressure.
    """
    submissions = (
        db.query(DBSubmission, DBProblem)
        .join(DBProblem, DBSubmission.problemId == DBProblem.problemId)
        .filter(DBSubmission.userId == user_id)
        .filter(DBSubmission.participantType.in_(["CONTESTANT", "OUT_OF_COMPETITION"]))
        .order_by(DBSubmission.submittedAt)
        .all()
    )

    problem_attempts = defaultdict(list)

    for sub, prob in submissions:
        problem_attempts[prob.problemId].append((sub, prob))

    topic_scores = defaultdict(list)
    solved_count = 0

    for problem_id, attempts_list in problem_attempts.items():

        attempts = 0
        first_ac_found = False
        attempts_until_ac = None
        latest_ac_time = None
        prob = None

        for sub, p in attempts_list:
            attempts += 1
            prob = p

            if sub.verdict == "OK":
                if not first_ac_found:
                    attempts_until_ac = attempts
                    first_ac_found = True
                latest_ac_time = sub.submittedAt

        if not first_ac_found:
            continue

        solved_count += 1

        difficulty_weight = calculate_problem_weight(prob.rating)
        recency_weight = calculate_recency_weight(latest_ac_time)
        attempt_penalty = calculate_attempt_penalty(attempts_until_ac)

        problem_score = difficulty_weight * recency_weight * attempt_penalty

        tags = prob.tags if prob.tags else ["general"]
        score_per_tag = problem_score / len(tags)

        for tag in tags:
            topic_scores[tag].append(score_per_tag)

    final_skills = {}
    for tag, scores in topic_scores.items():
        final_skills[tag] = calculate_diminishing_returns(scores)

    sorted_skills = dict(sorted(final_skills.items(), key=lambda x: x[1], reverse=True))

    return {
        "user_id": user_id,
        "type": "contest_only",
        "total_contest_solved": solved_count,
        "skill_vector": sorted_skills
    }