from types import SimpleNamespace
import math
import pytest
from metrics import measure, add_motion, summarize, ANGLE_METRICS


def pose():
    points = [SimpleNamespace(x=.5, y=.5, visibility=1, presence=1) for _ in range(33)]
    for i, x, y in [(11,.4,.3),(12,.6,.3),(23,.4,.6),(24,.6,.6),(15,.25,.3),(16,.75,.3)]:
        points[i].x=x;points[i].y=y
    return points


def test_relative_wrist_measurement_is_translation_invariant():
    points=pose(); a=measure(points,1000,500)
    for p in points:p.x+=.03;p.y+=.02
    b=measure(points,1000,500)
    assert a['right_wrist_relative_x']==pytest.approx(b['right_wrist_relative_x'])
    assert a['right_wrist_relative_y']==pytest.approx(b['right_wrist_relative_y'])
    assert a['torso_tilt']==pytest.approx(0)


def test_out_of_frame_or_nonfinite_landmarks_do_not_produce_metrics():
    points=pose();points[11].x=-.1
    result=measure(points,100,100)
    assert result['left_elbow'] is None
    assert result['torso_tilt'] is None
    points=pose();points[13].x=math.nan
    assert measure(points,100,100)['left_elbow'] is None


def motion_rows():
    return [{'seconds':i/10, 'left_wrist_relative_x':i/10, 'left_wrist_relative_y':0,
             'right_wrist_relative_x':0, 'right_wrist_relative_y':0,
             'left_knee':90+i, 'right_knee':90,
             **{k:90 for k in ANGLE_METRICS if k not in ['left_knee','right_knee']}} for i in range(20)]


def test_rates_use_real_time_and_do_not_bridge_missing_frames():
    rows=motion_rows()
    rows[8]['left_wrist_relative_x']=None
    add_motion(rows,10)
    assert rows[4]['left_wrist_speed_smoothed']==pytest.approx(1)
    assert rows[4]['left_knee_angular_speed_smoothed']==pytest.approx(10)
    assert rows[8]['left_wrist_speed'] is None
    assert rows[9]['left_wrist_speed'] is None
    assert rows[9]['left_wrist_speed_smoothed'] is None


def test_sparse_observations_do_not_generate_action_candidates():
    rows=motion_rows()
    for row in rows[2:]:
        for k in list(row):
            if k!='seconds':row[k]=None
    add_motion(rows,10)
    stats,events=summarize(rows,'tennis','left',10)
    assert stats['left_knee']['coverage']==.1
    assert events==[]


def test_skiing_and_racket_modes_have_distinct_candidate_metrics():
    rows=motion_rows(); add_motion(rows,10)
    _,ski=summarize(rows,'skiing','right',10)
    _,tennis=summarize(rows,'tennis','left',10)
    assert any(e.get('metric')=='left_knee' for e in ski)
    assert any(e.get('metric')=='left_wrist_speed_smoothed' for e in tennis)
    assert all(e['kind'] in {'candidate','context'} for e in tennis)


def test_static_detector_jitter_does_not_create_a_wrist_motion_peak():
    rows=motion_rows()
    for i,row in enumerate(rows):
        row['left_wrist_relative_x']=.005*(i%2)
        row['left_knee']=90+.1*(i%2)
    add_motion(rows,10)
    _,events=summarize(rows,'tennis','left',10)
    assert not any('speed' in e.get('metric','') for e in events)
