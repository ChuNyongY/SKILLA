from __future__ import annotations

import math

_Z_95 = 1.959963984540054


def wilson_interval_95(count: int, total: int) -> tuple[float, float]:
    """Return the two-sided Wilson 95% interval for a binomial proportion."""
    if type(count) is not int or type(total) is not int:
        raise TypeError("count and total must be integers")
    if total < 1 or not 0 <= count <= total:
        raise ValueError("count and total must satisfy 0 <= count <= total and total >= 1")
    proportion = count / total
    z_squared = _Z_95 * _Z_95
    denominator = 1.0 + z_squared / total
    center = (proportion + z_squared / (2.0 * total)) / denominator
    half_width = (_Z_95 / denominator) * math.sqrt(
        proportion * (1.0 - proportion) / total
        + z_squared / (4.0 * total * total)
    )
    return max(0.0, center - half_width), min(1.0, center + half_width)
