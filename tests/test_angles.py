from types import SimpleNamespace
import pytest
from analysis import angle, measure


def test_geometry():
    assert angle((0, 1), (0, 0), (1, 0)) == pytest.approx(90)
    assert angle((-1, 0), (0, 0), (1, 0)) == pytest.approx(180)
    assert angle((0, 0), (0, 0), (1, 0)) is None


def test_aspect_ratio_and_low_confidence():
    points = [SimpleNamespace(x=0, y=0, visibility=1, presence=1) for _ in range(33)]
    points[11].x, points[11].y = 0, 0
    points[13].x, points[13].y = .5, .5
    points[15].x, points[15].y = 1, 0
    assert measure(points, 200, 100)["left_elbow"] == pytest.approx(126.8698976)
    points[13].visibility = .1
    assert measure(points, 200, 100)["left_elbow"] is None
