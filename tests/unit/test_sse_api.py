import json

import pytest

from app.api import sse


class FakePubSub:
    def __init__(self, messages):
        self.messages = messages
        self.unsubscribed_channel = None
        self.closed = False

    async def listen(self):
        for message in self.messages:
            yield message

    async def unsubscribe(self, channel):
        self.unsubscribed_channel = channel

    async def aclose(self):
        self.closed = True


class FakeStore:
    def __init__(self, pubsub):
        self.pubsub = pubsub
        self.subscribed_research_id = None
        self.closed = False

    async def subscribe(self, research_id):
        self.subscribed_research_id = research_id
        return self.pubsub

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_event_stream_serializes_progress_and_closes_resources(monkeypatch):
    research_id = "research-123"
    pubsub = FakePubSub(
        [
            {"type": "subscribe"},
            {
                "type": "message",
                "data": json.dumps(
                    {
                        "type": "progress",
                        "status": "completed",
                        "progress": "completed",
                    }
                ),
            },
        ]
    )
    store = FakeStore(pubsub)
    monkeypatch.setattr(
        sse.RedisJobStore,
        "from_env",
        lambda: store,
    )

    events = [
        event
        async for event in sse.event_stream(research_id)
    ]

    assert events == [
        "event: progress\n"
        "data: {\"type\": \"progress\", \"status\": \"completed\", "
        "\"progress\": \"completed\"}\n\n"
    ]
    assert store.subscribed_research_id == research_id
    assert pubsub.unsubscribed_channel == f"research-events:{research_id}"
    assert pubsub.closed is True
    assert store.closed is True


@pytest.mark.asyncio
async def test_stream_endpoint_returns_sse_response():
    response = await sse.stream_research_progress("research-123")

    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
