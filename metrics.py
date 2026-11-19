"""Observable 2D kinematics. No force, pressure, injury risk or quality scores."""
import math
from statistics import median

JOINTS = {'left_elbow': (11, 13, 15), 'right_elbow': (12, 14, 16),
          'left_knee': (23, 25, 27), 'right_knee': (24, 26, 28),
          'left_hip': (11, 23, 25), 'right_hip': (12, 24, 26)}
ANGLE_METRICS = (*JOINTS, 'torso_tilt', 'shoulder_hip_line_angle')
SPORTS = {
    'tennis': {'name': '网球', 'focus': ['left_elbow', 'right_elbow', 'torso_tilt'],
               'prompts': ['回看手腕移动峰值前后，结合原片确认球拍与球的位置。', '同一机位比较准备、挥拍与随挥的姿态；候选峰值不等于击球时刻。']},
    'golf': {'name': '高尔夫', 'focus': ['left_elbow', 'left_hip', 'right_hip', 'torso_tilt'],
             'prompts': ['回看挥杆前后膝角与躯干投影的变化，结合原片确认球杆位置。', '肩髋连线的画面夹角受机位影响，不能作为真实转髋角或 X-factor。']},
    'skiing': {'name': '滑雪', 'focus': ['left_knee', 'right_knee', 'torso_tilt'],
               'prompts': ['比较左右膝角变化的时序，并回看对应弯道。', '普通录像不能测出外腿承重、雪板压力或真实重心位置；转弯与镜头移动都会影响投影。']},
}


def angle(a, b, c):
    if not all(math.isfinite(float(x)) for p in (a, b, c) for x in p[:2]):
        return None
    u = [a[i] - b[i] for i in range(2)]
    v = [c[i] - b[i] for i in range(2)]
    lengths = math.hypot(*u) * math.hypot(*v)
    if lengths < 1e-9:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x*y for x, y in zip(u, v)) / lengths))))


def visible(p, threshold):
    values = [p.x, p.y, p.visibility, p.presence]
    return (all(v is not None and math.isfinite(float(v)) for v in values)
            and 0 <= p.x <= 1 and 0 <= p.y <= 1
            and min(p.visibility, p.presence) >= threshold)


def measure(landmarks, width, height, threshold=.65):
    if len(landmarks) < 33 or width <= 0 or height <= 0:
        raise ValueError('需要 33 个关键点和有效的画面尺寸')
    result = {name: None for name in ANGLE_METRICS}
    for side in ('left', 'right'):
        result[f'{side}_wrist_relative_x'] = None
        result[f'{side}_wrist_relative_y'] = None
    for name, ids in JOINTS.items():
        points = [landmarks[i] for i in ids]
        if all(visible(p, threshold) for p in points):
            result[name] = angle(*[(p.x * width, p.y * height) for p in points])
    if all(visible(landmarks[i], threshold) for i in (11, 12, 23, 24)):
        xy = lambda i: (landmarks[i].x * width, landmarks[i].y * height)
        shoulder = tuple((xy(11)[i] + xy(12)[i]) / 2 for i in range(2))
        hip = tuple((xy(23)[i] + xy(24)[i]) / 2 for i in range(2))
        dx, dy = shoulder[0] - hip[0], shoulder[1] - hip[1]
        torso = math.hypot(dx, dy)
        if torso > max(width, height) * .02:
            result['torso_tilt'] = math.degrees(math.atan2(dx, -dy))
            a = math.degrees(math.atan2(xy(12)[1] - xy(11)[1], xy(12)[0] - xy(11)[0]))
            b = math.degrees(math.atan2(xy(24)[1] - xy(23)[1], xy(24)[0] - xy(23)[0]))
            if math.dist(xy(11), xy(12)) > 2 and math.dist(xy(23), xy(24)) > 2:
                result['shoulder_hip_line_angle'] = abs((a - b + 90) % 180 - 90)
            for side, index in [('left', 15), ('right', 16)]:
                if visible(landmarks[index], threshold):
                    result[f'{side}_wrist_relative_x'] = (xy(index)[0] - hip[0]) / torso
                    result[f'{side}_wrist_relative_y'] = (xy(index)[1] - hip[1]) / torso
    return result


def add_motion(rows, fps):
    """Adjacent-frame differences only; never infer movement across a missing detection."""
    for index, row in enumerate(rows):
        prev = rows[index - 1] if index else None
        dt = row['seconds'] - prev['seconds'] if prev else 0
        adjacent = prev is not None and 0 < dt <= 1.5 / fps
        for side in ('left', 'right'):
            key = f'{side}_wrist_speed'
            row[key] = None
            cols = [f'{side}_wrist_relative_x', f'{side}_wrist_relative_y']
            if adjacent and all(r.get(c) is not None for r in (prev, row) for c in cols):
                row[key] = math.hypot(*(row[c] - prev[c] for c in cols)) / dt
            key = f'{side}_knee_angular_speed'
            row[key] = None
            joint = f'{side}_knee'
            if adjacent and row.get(joint) is not None and prev.get(joint) is not None:
                row[key] = abs(row[joint] - prev[joint]) / dt
    # The median is only computed where three adjacent values exist. Gaps remain gaps.
    for key in ['left_wrist_speed', 'right_wrist_speed', 'left_knee_angular_speed', 'right_knee_angular_speed']:
        raw = [r[key] for r in rows]
        for i, row in enumerate(rows):
            window = raw[max(0, i-1):i+2]
            row[key + '_smoothed'] = median(window) if len(window) == 3 and all(v is not None for v in window) else None
    return rows


def summarize(rows, sport, side, fps):
    if sport not in SPORTS or side not in {'left', 'right'}:
        raise ValueError('无效的运动类型或惯用侧')
    stats = {}
    keys = [*ANGLE_METRICS, 'left_wrist_speed_smoothed', 'right_wrist_speed_smoothed',
            'left_knee_angular_speed_smoothed', 'right_knee_angular_speed_smoothed']
    for key in keys:
        values = [r[key] for r in rows if r.get(key) is not None]
        stats[key] = {'valid_frames': len(values), 'coverage': round(len(values) / len(rows), 3) if rows else 0,
                      'min': round(min(values), 3) if values else None, 'max': round(max(values), 3) if values else None,
                      'median': round(median(values), 3) if values else None,
                      'unit': 'torso_lengths/s' if 'wrist_speed' in key else 'degrees/s' if 'angular_speed' in key else 'degrees'}
    events = []
    def has_motion(metric):
        # Small, explicit display gates suppress static-detector jitter. These are
        # visualization heuristics, not biomechanical quality thresholds.
        if 'wrist_speed' in metric:
            prefix = metric.split('_wrist')[0]
            ranges = []
            for axis in ('x', 'y'):
                values = sorted(r[f'{prefix}_wrist_relative_{axis}'] for r in rows if r.get(f'{prefix}_wrist_relative_{axis}') is not None)
                ranges.append(values[int((len(values)-1)*.9)] - values[int((len(values)-1)*.1)] if values else 0)
            return math.hypot(*ranges) >= .1
        if 'knee_angular_speed' in metric:
            joint = metric.split('_knee')[0] + '_knee'
            values = sorted(r[joint] for r in rows if r.get(joint) is not None)
            return bool(values) and values[int((len(values)-1)*.9)] - values[int((len(values)-1)*.1)] >= 5
        return True

    def event_extreme(metric, kind, title):
        candidates = [(i, r[metric]) for i, r in enumerate(rows) if r.get(metric) is not None]
        # Suppress conclusions based on a tiny number of incidental detections.
        if len(candidates) < max(5, len(rows) * .5) or not has_motion(metric):
            return
        index, value = (min if kind == 'min' else max)(candidates, key=lambda x: x[1])
        if 'speed' in metric and value < .01:
            return
        events.append({'title': title, 'metric': metric, 'frame_index': index,
                       'seconds': rows[index]['seconds'], 'value': round(value, 3), 'kind': 'candidate'})
    if sport == 'skiing':
        event_extreme('left_knee', 'min', '左膝投影角最小候选帧')
        event_extreme('right_knee', 'min', '右膝投影角最小候选帧')
        event_extreme('left_knee_angular_speed_smoothed', 'max', '左膝角变化速度峰值候选')
        event_extreme('right_knee_angular_speed_smoothed', 'max', '右膝角变化速度峰值候选')
    else:
        event_extreme(f'{side}_wrist_speed_smoothed', 'max', '惯用侧手腕相对移动峰值候选')
        if events:
            peak = events[0]
            for offset, title in [(-.3, '候选峰值前约 0.3 秒'), (.3, '候选峰值后约 0.3 秒')]:
                index = max(0, min(len(rows)-1, peak['frame_index'] + round(offset * fps)))
                if index != peak['frame_index']:
                    events.append({'title': title, 'frame_index': index, 'seconds': rows[index]['seconds'], 'kind': 'context'})
        event_extreme(f'{side}_knee_angular_speed_smoothed', 'max', '惯用侧膝角变化速度峰值候选')
    for metric in SPORTS[sport]['focus'][:2]:
        event_extreme(metric, 'min', metric + ' 最小投影角候选')
    # Do not duplicate an identical frame/metric candidate.
    unique = {}
    for event in events:
        unique.setdefault((event['frame_index'], event.get('metric')), event)
    return stats, list(unique.values())[:6]
