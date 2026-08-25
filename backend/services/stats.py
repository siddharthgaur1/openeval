def welch_t_test(a: list[float], b: list[float]) -> dict:
    """Welch's t-test (unequal variance). Returns {statistic, p_value}; p_value is
    None if either sample has fewer than 2 points (not enough data to test).
    """
    if len(a) < 2 or len(b) < 2:
        return {"statistic": None, "p_value": None}
    from scipy import stats

    statistic, p_value = stats.ttest_ind(a, b, equal_var=False)
    return {"statistic": float(statistic), "p_value": float(p_value)}


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)
