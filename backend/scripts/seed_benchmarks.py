import os
import json
import asyncio
from datetime import datetime

from database import SessionLocal
from models import DBBenchmarkSample, DBPlatformProfile
from services.sync import sync_codeforces_data
from services.compute_skill import calculate_skill_vector


SEED_FOLDER = "benchmark_seed"


def get_bucket_from_filename(filename: str):
    name = filename.replace(".json", "")
    return name.replace("_", "-")


async def process_handle(handle, bucket, db):

    user_id = f"seed_{handle}"

    # Check if already seeded
    existing = db.query(DBBenchmarkSample).filter(
        DBBenchmarkSample.userId == user_id
    ).first()

    if existing:
        print(f"Skipping {handle} (already seeded)")
        return

    print(f"\nProcessing {handle}")

    # Create temporary platform profile
    profile = DBPlatformProfile(
        userId=user_id,
        platform="codeforces",
        handle=handle,
        currentRating=int(bucket.split("-")[0]) if "-" in bucket else 2200,
        maxRating=int(bucket.split("-")[1]) if "-" in bucket else 3000,
        lastSyncedAt=datetime.utcnow()
    )

    db.add(profile)
    db.commit()

    # Sync CF submissions
    await sync_codeforces_data(handle, user_id, db)

    # Compute skill vector
    skill_vector, _ = calculate_skill_vector(user_id, db)

    samples = []

    for topic, score in skill_vector.items():

        samples.append(
            DBBenchmarkSample(
                userId=user_id,
                ratingBucket=bucket,
                topic=topic,
                score=score,
                source="seed",
                createdAt=datetime.utcnow()
            )
        )

    if samples:
        db.add_all(samples)
        db.commit()

    print(f"Seeded {handle}")


async def main():

    db = SessionLocal()

    for file in os.listdir(SEED_FOLDER):

        if not file.endswith(".json"):
            continue

        bucket = get_bucket_from_filename(file)

        file_path = os.path.join(SEED_FOLDER, file)

        print(f"\n===== Processing bucket {bucket} =====")

        with open(file_path, "r") as f:
            handles = json.load(f)

        for handle in handles:
            await process_handle(handle, bucket, db)

    db.close()

    print("\nBenchmark seed completed")


if __name__ == "__main__":
    asyncio.run(main())