import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from models import DBSubmission, DBContest
    from services.anomaly import detect_concept_gap_anomalies
    from services.sync import process_cf_submission, sync_codeforces_data
    from services.codeforces import fetch_contest_info
    print("Part 1 Modules imported successfully.")
except Exception as e:
    print("Import error in Part 1:", e)
    sys.exit(1)
