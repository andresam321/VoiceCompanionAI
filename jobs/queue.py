# jobs/queue.py
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.job import Job

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_SECONDS = 60


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def enqueue(
    db: AsyncSession,
    job_type: str,
    payload: dict,
    max_attempts: int = 3,
) -> Job:
    job = Job(
        job_type=job_type,
        payload=payload,
        max_attempts=max_attempts,
    )
    db.add(job)
    await db.flush()
    logger.info("Enqueued job %s [%s]", job.id, job.job_type)
    return job


async def dequeue(
    db: AsyncSession,
    worker_id: str,
    job_types: list[str] | None = None,
) -> Job | None:
    """
    Claims next runnable job.
    Also recovers stale processing jobs.
    """

    now = utcnow()
    stale_cutoff = now - timedelta(seconds=LOCK_TIMEOUT_SECONDS)

    stmt = (
        select(Job)
        .where(
            or_(
                # Normal pending jobs ready to run
                and_(
                    Job.status == "pending",
                    Job.run_after <= now,
                ),
                # Stale locked jobs
                and_(
                    Job.status == "processing",
                    Job.locked_at <= stale_cutoff,
                ),
            )
        )
        .order_by(Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )

    if job_types:
        stmt = stmt.where(Job.job_type.in_(job_types))

    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        return None

    job.status = "processing"
    job.locked_by = worker_id
    job.locked_at = now
    job.attempts += 1

    await db.flush()

    logger.info(
        "Worker %s claimed job %s [%s] trace=%s",
        worker_id,
        job.id,
        job.job_type,
        job.trace_id,
    )

    return job


async def complete_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    result: dict | None = None,
) -> None:
    stmt = (
        update(Job)
        .where(Job.id == job_id)
        .values(
            status="complete",
            result=result or {},
            locked_by=None,
            locked_at=None,
        )
    )
    await db.execute(stmt)

    logger.info("Job %s completed", job_id)


async def fail_job(
    db: AsyncSession,
    job: Job,
    error: str,
) -> None:
    """
    Schedules retry with backoff or marks permanently failed.
    No sleeping here.
    """

    now = utcnow()

    if job.attempts < job.max_attempts:
        backoff_seconds = 2 ** job.attempts
        job.status = "pending"
        job.run_after = now + timedelta(seconds=backoff_seconds)
        job.locked_by = None
        job.locked_at = None
        job.error = error

        logger.warning(
            "Job %s retry %d/%d in %ds trace=%s",
            job.id,
            job.attempts,
            job.max_attempts,
            backoff_seconds,
            job.trace_id,
        )
    else:
        job.status = "failed"
        job.error = error
        job.locked_by = None
        job.locked_at = None

        logger.error(
            "Job %s permanently failed after %d attempts trace=%s",
            job.id,
            job.attempts,
            job.trace_id,
        )

    await db.flush()