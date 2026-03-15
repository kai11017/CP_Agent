import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from services.gap_analysis import get_performance_report
    from services.compute_skill import calculate_skill_vector
    from services.sync import sync_codeforces_data
    from services.topic_learning import recalculate_user_topic_weights
    from services.codeforces import fetch_user_contests
    print("All modules imported successfully.")
except Exception as e:
    print("Import error:", e)
    sys.exit(1)

# to quickly just verify the new functions made are usable or not