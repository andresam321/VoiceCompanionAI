# jobs/queue.py
"""
Database-backed job queue with SELECT FOR UPDATE SKIP LOCKED,
retry logic, and exponential backoff.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.job import Job

logger = logging.getLogger(__name__)


async def enqueue(
    db: AsyncSession,
    job_type: str,
    payload: dict,
    max_attempts: int = 3,
) -> Job:
    """Insert a new job into the queue."""
    job = Job(
        job_type=job_type,
        payload=payload,
        max_attempts=max_attempts,
    )
    db.add(job)
    await db.flush()
    logger.info("Enqueued job %s [%s]", job.id, job_type)
    return job


async def dequeue(
    db: AsyncSession,
    worker_id: str,
    job_types: list[str] | None = None,
) -> Job | None:
    """
    Claim the next pending job using SELECT FOR UPDATE SKIP LOCKED.
    Returns None if no jobs are available.
    """
    stmt = (
        select(Job)
        .where(Job.status == "pending")
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

    job.status = "locked"
    job.locked_by = worker_id
    job.attempts += 1
    await db.flush()
    logger.info("Worker %s claimed job %s [%s]", worker_id, job.id, job.job_type)
    return job


async def complete_job(db: AsyncSession, job_id: uuid.UUID, result: dict | None = None) -> None:
    """Mark a job as complete."""
    stmt = (
        update(Job)
        .where(Job.id == job_id)
        .values(status="complete", result=result or {})
    )
    await db.execute(stmt)
    logger.info("Job %s completed", job_id)


async def fail_job(db: AsyncSession, job_id: uuid.UUID, error: str) -> None:
    """Mark a job as failed. Re-enqueue if under max attempts."""
    stmt = select(Job).where(Job.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        return

    if job.attempts < job.max_attempts:
        # Re-enqueue with backoff
        job.status = "pending"
        job.locked_by = None
        job.error = error
        backoff = 2 ** job.attempts
        logger.warning("Job %s failed (attempt %d/%d), retry in %ds: %s",
                        job.id, job.attempts, job.max_attempts, backoff, error)
        await db.flush()
        await asyncio.sleep(backoff)
    else:
        job.status = "failed"
        job.error = error
        logger.error("Job %s permanently failed after %d attempts: %s",
                      job.id, job.attempts, error)
        await db.flush()
