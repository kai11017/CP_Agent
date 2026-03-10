from database import SessionLocal
from services.benchmarks import recompute_benchmarks

db = SessionLocal()

result = recompute_benchmarks(db)

print(result)

db.close()