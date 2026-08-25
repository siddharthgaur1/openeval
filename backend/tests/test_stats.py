from services.stats import percentile


def test_percentile_median():
    assert percentile([1, 2, 3, 4, 5], 0.5) == 3


def test_percentile_empty():
    assert percentile([], 0.95) == 0.0


def test_percentile_p99_upper_bound():
    values = list(range(1, 101))
    assert percentile(values, 0.99) >= 98
