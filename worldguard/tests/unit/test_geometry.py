import math

import pytest

from worldguard.verifier.geometry import segment_rectangle_distance


@pytest.mark.parametrize(
    "a,b,rect,expected",
    [
        ((0, 1), (4, 1), (2, 0, 2.1, 2), 0),  # thin wall, safe endpoints
        ((0, 0), (2, 2), (1, 0, 2, 1), 0),  # diagonal corner contact
        ((0, 2), (4, 2), (1, 0, 2, 1), 1),
        ((0, 0), (0, 0), (1, 1, 2, 2), math.sqrt(2)),
        ((1.5, 1.5), (1.5, 1.5), (1, 1, 2, 2), 0),
        ((0, 0), (1, 0), (2, 1, 3, 2), math.sqrt(2)),
        ((3, 3), (4, 4), (0, 0, 1, 1), math.sqrt(8)),
    ],
)
def test_segment_rectangle(a, b, rect, expected):
    assert segment_rectangle_distance(a, b, rect)[0] == pytest.approx(expected, abs=1e-12)
    assert segment_rectangle_distance(b, a, rect)[0] == pytest.approx(expected, abs=1e-12)
