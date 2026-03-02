import asyncio
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from services.sync import sync_codeforces_data
from services.compute_skill import compute_user_vector
from services.benchmarks import compute_benchmarks_for_bucket
from models import DBUser, DBPlatformProfile
from uuid import uuid4
from datetime import datetime

# Initialize the database tables if they don't exist
Base.metadata.create_all(bind=engine)

# A mix of world-class and high-rated handles to build a strong benchmark
HANDLES = [
    "tourist", "Benq", "Radewoosh", "ksun48", "um_nik", 
    "neal", "Petr", "maroonrk", "Egor", "apiad",
    "vovuh", "awoo", "Errichto", "Geothermal", "scott_wu"
]

async def seed_data():
    db = SessionLocal()
    print("Starting Bulk Ingestion...")

    for handle in HANDLES:
        print(f"--- Processing {handle} ---")
        
        # 1. Create a dummy internal user for this handle
        existing_user = db.query(DBPlatformProfile).filter(DBPlatformProfile.handle == handle).first()
        if not existing_user:
            new_user = DBUser(
                userId=str(uuid4()),
                name=handle,
                email=f"{handle}@example.com",
                createdAt=datetime.utcnow()
            )
            db.add(new_user)
            db.commit()
            user_id = new_user.userId
            
            # Link Profile
            profile = DBPlatformProfile(
                userId=user_id,
                platform="codeforces",
                handle=handle,
                currentRating=3000, # Placeholder, sync will update this
            )
            db.add(profile)
            db.commit()
        else:
            user_id = existing_user.userId

        # 2. Sync their submissions (Rule 2: Incremental)
        try:
            print(f"Fetching submissions for {handle}...")
            await sync_codeforces_data(handle, user_id, db)
            
            # 3. Compute their Skill Vector
            print(f"Calculating skill vector for {handle}...")
            compute_user_vector(user_id, db)
        except Exception as e:
            print(f"Failed to sync {handle}: {e}")

    # 4. Final Step: Generate Benchmarks for the High-Rating Bucket
    print("--- Calculating Final Benchmarks ---")
    # We'll calculate for the 2800-3000+ range where these legends live
    compute_benchmarks_for_bucket(2000, 4000, db)
    
    print("Seed Complete! Your database is now populated with elite data.")
    db.close()

if __name__ == "__main__":
    asyncio.run(seed_data())