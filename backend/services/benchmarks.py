import numpy as np
from sqlalchemy.orm import Session
from collections import defaultdict
from datetime import datetime

from models import DBBenchmarkSample, DBBenchmark


def recompute_benchmarks(db: Session):
    """
    Convert benchmark_samples → benchmark statistics
    """

    # fetch all samples
    samples = db.query(DBBenchmarkSample).all()

    bucket_topic_scores = defaultdict(list)

    for sample in samples:
        key = (sample.ratingBucket, sample.topic)
        bucket_topic_scores[key].append(sample.score)

    # clear old benchmark stats
    db.query(DBBenchmark).delete()

    benchmark_rows = []

    for (bucket, topic), scores in bucket_topic_scores.items():

        scores_array = np.array(scores)

        avg = float(np.mean(scores_array))
        p75 = float(np.percentile(scores_array, 75))
        p90 = float(np.percentile(scores_array, 90))

        benchmark_rows.append(
            DBBenchmark(
                ratingBucket=bucket,
                topic=topic,
                avgScore=round(avg, 2),
                p75Score=round(p75, 2),
                p90Score=round(p90, 2),
                lastComputed=datetime.utcnow()
            )
        )

    if benchmark_rows:
        db.add_all(benchmark_rows)
        db.commit()

    return {
        "buckets_processed": len(set([b.ratingBucket for b in benchmark_rows])),
        "topics_processed": len(benchmark_rows)
    }