import pytest
from fastapi.testclient import TestClient

from app.sse_app import app

client = TestClient(app)


def test_post_research_creates_job():
    resp = client.post("/research", json={"question": "What is pgvector HNSW indexing?"})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert "id" in data
    assert data["question"] == "What is pgvector HNSW indexing?"
    assert data["status"] == "pending"

    # Cleanup
    client.get(f"/research/{data['id']}")  # Verify exists


def test_post_research_rejects_empty_question():
    resp = client.post("/research", json={"question": ""})
    assert resp.status_code == 422 or resp.status_code == 400


def test_post_research_rejects_missing_question():
    resp = client.post("/research", json={})
    assert resp.status_code == 422


def test_get_research_status_not_found():
    resp = client.get("/research/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_get_research_invalid_id_format():
    resp = client.get("/research/not-a-uuid")
    assert resp.status_code == 400


def test_get_report_not_found_for_pending_job():
    # Create a pending job
    create = client.post("/research", json={"question": "Test report not ready"})
    assert create.status_code == 201
    job_id = create.json()["id"]

    resp = client.get(f"/research/{job_id}/report")
    # Should be 404 because not completed
    assert resp.status_code == 404
    assert "not yet available" in resp.text.lower() or "not found" in resp.text.lower()


def test_health_and_metrics_endpoints():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "research_runs_total" in metrics.text


def test_sse_stream_endpoint_exists():
    # Check via OpenAPI that the SSE route is registered, without actually streaming
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/research/{research_id}/stream" in paths
