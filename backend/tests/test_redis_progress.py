from unittest.mock import patch

from core.redis import progress_channel, publish_progress


def test_progress_channel_format():
    assert progress_channel("abc-123") == "eval-progress:abc-123"


@patch("core.redis.redis_client")
def test_publish_progress_serializes_and_publishes(mock_client):
    publish_progress("abc-123", {"status": "running", "completed_rows": 2})
    mock_client.publish.assert_called_once()
    channel, payload = mock_client.publish.call_args[0]
    assert channel == "eval-progress:abc-123"
    assert '"status": "running"' in payload
