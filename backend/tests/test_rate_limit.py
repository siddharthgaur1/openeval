from unittest.mock import MagicMock, patch

from services.rate_limit import check_rate_limit


@patch("services.rate_limit.redis_client")
def test_allows_when_under_limit(mock_redis):
    pipe = MagicMock()
    pipe.execute.return_value = [None, 2, None, None]  # 2 requests already in window
    mock_redis.pipeline.return_value = pipe

    allowed, remaining = check_rate_limit("user-1", limit=5, window_seconds=60)
    assert allowed is True
    assert remaining == 2


@patch("services.rate_limit.redis_client")
def test_blocks_when_at_limit(mock_redis):
    pipe = MagicMock()
    pipe.execute.return_value = [None, 5, None, None]  # already at the limit
    mock_redis.pipeline.return_value = pipe

    allowed, remaining = check_rate_limit("user-1", limit=5, window_seconds=60)
    assert allowed is False
    assert remaining == 0
    mock_redis.zrem.assert_called_once()
