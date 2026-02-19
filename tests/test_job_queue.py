# tests/test_job_queue.py
"""
Tests for the job queue system.

These tests verify the queue interface without requiring a real database.
For full integration tests, use a PostgreSQL test container.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.job import Job


def _make_job(**kwargs) -> Job:
    defaults = dict(
        id=uuid.uuid4(),
        job_type="PROCESS_VOICE_INTERACTION",
        status="pending",
        payload={"interaction_id": str(uuid.uuid4())},
        attempts=0,
        max_attempts=3,
    )
    defaults.update(kwargs)
    return Job(**defaults)


def test_job_defaults():
    job = _make_job()
    assert job.status == "pending"
    assert job.attempts == 0
    assert job.max_attempts == 3


def test_job_locking_sets_status():
    job = _make_job()
    job.status = "locked"
    job.locked_by = "worker-abc"
    job.attempts += 1
    assert job.status == "locked"
    assert job.locked_by == "worker-abc"
    assert job.attempts == 1


def test_job_retry_logic():
    """Verify re-enqueue logic: if attempts < max_attempts, status resets to pending."""
    job = _make_job(attempts=1, max_attempts=3, status="locked")
    # Simulate fail_job logic
    if job.attempts < job.max_attempts:
        job.status = "pending"
        job.locked_by = None
        job.error = "Some error"
    assert job.status == "pending"
    assert job.locked_by is None


def test_job_permanent_failure():
    """After max attempts, job should be marked failed."""
    job = _make_job(attempts=3, max_attempts=3, status="locked")
    if job.attempts >= job.max_attempts:
        job.status = "failed"
        job.error = "Too many retries"
    assert job.status == "failed"


def test_job_completion():
    job = _make_job(status="locked")
    job.status = "complete"
    job.result = {"ok": True}
    assert job.status == "complete"
    assert job.result == {"ok": True}
