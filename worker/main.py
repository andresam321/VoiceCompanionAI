# worker/main.py
"""
Background worker: polls the job queue and dispatches to handlers.
"""
from __future__ import annotations

import asyncio
import logging
import os
import platform
import sys
import traceback
import uuid

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api.app.config import get_settings
from db.session import get_db
from jobs.queue import complete_job, dequeue, fail_job
from jobs.handlers import HANDLERS
from services.observability import log_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")


WORKER_ID = f"worker-{platform.node()}-{uuid.uuid4().hex[:8]}"


async def run_loop() -> None:
    settings = get_settings()
    logger.info(
        "Worker %s starting (poll=%.1fs)",
        WORKER_ID,
        settings.worker_poll_interval,
    )

    while True:
        try:
            async for db in get_db():
                job = await dequeue(db, worker_id=WORKER_ID)

                if job is None:
                    break  # no jobs, sleep and retry

                job_id = str(job.id)
                job_type = job.job_type
                payload = job.payload
                handler = HANDLERS.get(job.job_type)

                if handler is None:
                    await fail_job(
                        db,
                        job.id,
                        f"Unknown job type: {job.job_type}",
                    )
                    await db.commit()
                    continue

                try:
                    result = await handler(db, job.payload)

                    await complete_job(db, job.id, result)

                    await db.commit()  # ✅ SUCCESS COMMIT

                except Exception as exc:
                    tb = traceback.format_exc()

                    # Revert any partial writes from the handler
                    await db.rollback()

                    # Mark job failed / schedule retry
                    await fail_job(db, job, f"{exc}\n{tb}")

                    # Log failure event (optional but good)
                    await log_event(
                        db,
                        "job_failed",
                        "error",
                        source="worker",
                        metadata={
                            "job_id": str(job.id),
                            "job_type": job.job_type,
                            "error": str(exc),
                        },
                    )

                    # Persist failure record + event
                    await db.commit()

        except Exception as exc:
            logger.exception("Worker loop error: %s", exc)

        await asyncio.sleep(settings.worker_poll_interval)


def main() -> None:
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
