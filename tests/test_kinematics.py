import math

from src.analysis.kinematics import calculate_angle, calculate_distance


def point(x: float, y: float) -> dict[str, float]:
    return {"pixel_x": x, "pixel_y": y}


def test_calculate_angle_returns_expected_right_angle():
    angle = calculate_angle(point(1, 0), point(0, 0), point(0, 1))

    assert angle == 90.0


def test_calculate_angle_returns_nan_for_missing_point():
    angle = calculate_angle(point(1, 0), None, point(0, 1))

    assert math.isnan(angle)


def test_calculate_angle_returns_nan_for_overlapping_point():
    angle = calculate_angle(point(0, 0), point(0, 0), point(0, 1))

    assert math.isnan(angle)


def test_calculate_distance_uses_pixel_coordinates():
    distance = calculate_distance(point(0, 0), point(3, 4))

    assert distance == 5.0
