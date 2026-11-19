import json
import math
from types import SimpleNamespace

from analysis import frame_observation, landmark_record
from metrics import add_motion


def test_multiplayer_and_missing_frames_cannot_bridge_a_movement():
    def pose(x):
        return [SimpleNamespace(x=x, y=.5, visibility=1., presence=1.) for _ in range(33)]
    rows = []
    for t, poses in [(0., [pose(.2)]), (.1, [pose(.3), pose(.7)]), (.2, []), (.3, [pose(.8)])]:
        row, category = frame_observation(poses, t, 640, 480, .65)
        if t in (.1, .2):
            assert category in {'multiple_people', 'no_pose'}
            assert all(v is None for k, v in row.items() if k not in {'seconds', 'pose_count'})
        rows.append(row)
    add_motion(rows, 10)
    assert all(r['right_wrist_speed'] is None for r in rows)


def test_nonfinite_model_values_export_as_null_and_do_not_abort_video():
    points = [SimpleNamespace(x=.5, y=.5, visibility=1., presence=1.) for _ in range(33)]
    points[13].x = math.nan
    points[14].visibility = math.inf
    points[15].presence = None
    row, _ = frame_observation([points], 1, 640, 480, .65)
    assert row['left_elbow'] is None and row['right_elbow'] is None
    data = json.loads(json.dumps(landmark_record(points), allow_nan=False))
    assert data[13]['x'] is None and data[14]['visibility'] is None and data[15]['presence'] is None


def test_crop_bounds_reject_nan_empty_regions_and_out_of_frame_boxes():
    import pytest
    from analysis import crop_filter
    for crop in [(0, 0, 0, 100), (50, 0, 60, 100), (0, -1, 100, 100), (0, 0, math.nan, 100), (0, 0, 100)]:
        with pytest.raises(ValueError):
            crop_filter(crop)
    assert 'crop=' in crop_filter((25, 40, 35, 35))
