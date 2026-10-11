import asyncio
import uuid

import pytest

from app.db.postgres import create_pool
from app.db.repositories import ResearchJobRepository


@pytest.fixture(autouse=True)
def _clean_pending():
    # Ensure each test starts with no pending/running jobs to avoid cross-test flakiness
    async def _clean():
        pool = await create_pool()
        try:
            await pool.execute("DELETE FROM report_evaluations USING reports WHERE report_evaluations.report_id = reports.id AND reports.job_id IN (SELECT id FROM research_jobs WHERE status IN ('pending', 'running'))")
            await pool.execute("DELETE FROM reports WHERE job_id IN (SELECT id FROM research_jobs WHERE status IN ('pending', 'running'))")
            await pool.execute("DELETE FROM research_jobs WHERE status IN ('pending', 'running')")
        finally:
            await pool.close()

    asyncio.run(_clean())
    yield
    asyncio.run(_clean())


@pytest.mark.asyncio
async def test_claim_sets_lease_and_worker_id():
    pool = await create_pool()
    try:
        repo = ResearchJobRepository(pool)
        question = f"Lease test {uuid.uuid4()}"
        job_id = await repo.create(question=question)

        claimed = await repo.claim_next_pending(worker_id="worker-1", lease_seconds=60)
        assert claimed == job_id

        job = await repo.get_by_id(job_id)
        assert job["status"] == "running"
        assert job["worker_id"] == "worker-1"
        assert job["lease_expires_at"] is not None
        assert job["retry_count"] == 0

        await pool.execute("DELETE FROM research_jobs WHERE id=$1", job_id)
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_heartbeat_refreshes_lease():
    pool = await create_pool()
    try:
        repo = ResearchJobRepository(pool)
        await pool.execute("DELETE FROM research_jobs WHERE status='pending'")
        question = f"Heartbeat test {uuid.uuid4()}"
        job_id = await repo.create(question=question)
        await repo.claim_next_pending(worker_id="worker-1", lease_seconds=60)

        job1 = await repo.get_by_id(job_id)
        lease1 = job1["lease_expires_at"]

        await asyncio.sleep(0.1)
        await repo.heartbeat(job_id, worker_id="worker-1", lease_seconds=60)

        job2 = await repo.get_by_id(job_id)
        assert job2["lease_expires_at"] > lease1

        # Heartbeat with wrong worker should not update
        await repo.heartbeat(job_id, worker_id="worker-2", lease_seconds=60)
        job3 = await repo.get_by_id(job_id)
        assert job3["lease_expires_at"] == job2["lease_expires_at"]
        assert job3["worker_id"] == "worker-1"

        await pool.execute("DELETE FROM research_jobs WHERE id=$1", job_id)
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_expired_lease_can_be_reclaimed():
    pool = await create_pool()
    try:
        repo = ResearchJobRepository(pool)
        await pool.execute("DELETE FROM research_jobs WHERE status='pending'")
        question = f"Expired lease test {uuid.uuid4()}"
        job_id = await repo.create(question=question)

        # Claim with very short lease
        claimed = await repo.claim_next_pending(worker_id="worker-1", lease_seconds=1)
        assert claimed == job_id

        # Wait for lease to expire
        await asyncio.sleep(1.5)

        # Another worker should be able to claim it
        repo2 = ResearchJobRepository(pool)
        claimed2 = await repo2.claim_next_pending(worker_id="worker-2", lease_seconds=60)
        assert claimed2 == job_id

        job = await repo.get_by_id(job_id)
        assert job["worker_id"] == "worker-2"
        assert job["retry_count"] == 1

        await pool.execute("DELETE FROM research_jobs WHERE id=$1", job_id)
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_running_job_with_valid_lease_not_reclaimed():
    pool = await create_pool()
    try:
        repo = ResearchJobRepository(pool)
        await pool.execute("DELETE FROM research_jobs WHERE status='pending'")
        question = f"Valid lease test {uuid.uuid4()}"
        job_id = await repo.create(question=question)

        claimed = await repo.claim_next_pending(worker_id="worker-1", lease_seconds=60)
        assert claimed == job_id

        # Try to claim with another worker immediately - should get None (no pending, and running lease not expired)
        repo2 = ResearchJobRepository(pool)
        claimed2 = await repo2.claim_next_pending(worker_id="worker-2", lease_seconds=60)
        assert claimed2 is None

        # Original job should still be running with worker-1
        job = await repo.get_by_id(job_id)
        assert job["status"] == "running"
        assert job["worker_id"] == "worker-1"

        await pool.execute("DELETE FROM research_jobs WHERE id=$1", job_id)
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pending_takes_precedence_over_expired_running():
    pool = await create_pool()
    try:
        repo = ResearchJobRepository(pool)
        # Create an expired running job first (oldest)
        expired_id = await repo.create(question=f"Expired lease test 2 {uuid.uuid4()}")
        await repo.claim_next_pending(worker_id="worker-1", lease_seconds=1)
        await asyncio.sleep(1.5)
        # Now create two pending jobs (newer than expired)
        pending_id = await repo.create(question=f"Pending lease test {uuid.uuid4()}")
        pending_id2 = await repo.create(question=f"Pending lease test {uuid.uuid4()}")

        # Now we have: expired_id (expired running, oldest), pending_id (older pending), pending_id2 (newer pending)
        # The next claim should prefer pending (pending_id) over expired, and oldest pending first
        claimed = await repo.claim_next_pending(worker_id="worker-2", lease_seconds=60)
        assert claimed == pending_id

        # Next claim should get pending_id2
        claimed2 = await repo.claim_next_pending(worker_id="worker-2", lease_seconds=60)
        assert claimed2 == pending_id2

        # Next claim should get expired_id (now that all pendings are claimed)
        claimed3 = await repo.claim_next_pending(worker_id="worker-2", lease_seconds=60)
        assert claimed3 == expired_id

        # Cleanup
        for jid in [pending_id, expired_id, pending_id2, claimed, claimed2, claimed3]:
            if jid:
                await pool.execute("DELETE FROM report_evaluations WHERE job_id=$1", jid)
                await pool.execute("DELETE FROM reports WHERE job_id=$1", jid)
                await pool.execute("DELETE FROM research_jobs WHERE id=$1", jid)
    finally:
        await pool.close()
