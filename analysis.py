"""Single-person sports video observation using MediaPipe and 2D geometry."""
import csv
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from statistics import median
import subprocess
import tempfile
import time
import urllib.request
import uuid

from metrics import ANGLE_METRICS, JOINTS, SPORTS, add_motion, angle, measure, summarize, visible

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / '.local' / 'runs'
MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task'
MODEL_SHA256 = '59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a'
DISPLAY_FILTER = r'scale=w=trunc(oh*dar/2)*2:h=trunc(min(ih\,min(960\,960/dar))/2)*2,setsar=1'
EDGES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24),
         (23, 24), (23, 25), (25, 27), (24, 26), (26, 28), (27, 29), (29, 31), (28, 30), (30, 32)]
LIMITATIONS = [
    '所有角度和速度均来自二维画面投影，受机位、遮挡、镜头移动和透视影响。',
    '手腕速度以画面中的躯干长度归一化，不是米/秒，也不是球拍或球杆速度。',
    '时间和速度基于视频播放时间轴；慢动作、加速或剪辑视频不能直接代表真实动作速度。',
    '关键帧是数值极值候选，不代表击球时刻、挥杆分期或转弯完成。',
    '不能据此测量真实力量、关节力矩、足底/雪板压力、真实重心或给出伤病诊断。',
    '最多处理前 60 秒；输出视频无音轨。低置信度、画面外和检测到多人的帧留空，不跨缺失帧插值。',
    '检测器可能漏掉其他人；pose_count=1 不保证画面实际只有一人，请先确认录像为单人。',
    '请使用同一人、无剪辑、固定机位录像。模型不提供人物身份追踪；突然切换人物可能无法辨识。',
]


def ffmpeg_path():
    configured = os.getenv('FFMPEG_BINARY')
    found = shutil.which(configured or 'ffmpeg')
    if found:
        return found
    if configured:
        raise ValueError('FFMPEG_BINARY 指向的程序不存在')
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(args, log):
    with log.open('a', encoding='utf-8') as stream:
        try:
            subprocess.run([ffmpeg_path(), '-hide_banner', '-nostdin', '-y', *map(str, args)],
                           stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise RuntimeError('视频预处理/导出超过 5 分钟，已停止；可缩短视频后重试') from None
        except subprocess.CalledProcessError:
            raise RuntimeError(f'视频解码或编码失败，请查看 {log}') from None


@contextmanager
def analysis_lock():
    import fcntl
    RUNS.mkdir(parents=True, exist_ok=True)
    with (RUNS.parent / 'analysis.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('已有视频正在分析，请等它结束') from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def model_file():
    override = os.environ.get('POSE_MODEL_PATH')
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise ValueError('POSE_MODEL_PATH 指向的文件不存在')
        return path
    path = ROOT / '.local' / 'models' / 'pose_landmarker_lite.task'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.download')
        try:
            with urllib.request.urlopen(MODEL_URL, timeout=60) as response, temp.open('wb') as stream:
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
            if hashlib.sha256(temp.read_bytes()).hexdigest() != MODEL_SHA256:
                raise RuntimeError('姿态模型下载未通过 SHA-256 校验')
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
        raise RuntimeError('姿态模型缓存校验失败，请移走损坏文件后重新下载')
    return path


def frame_observation(poses, seconds, width, height, threshold):
    """Keep missing and ambiguous observations empty before computing derivatives."""
    row = {'seconds': round(seconds, 6), 'pose_count': len(poses), 'subject_height_pixels': None,
           **{k: None for k in ANGLE_METRICS},
           **{f'{s}_wrist_relative_{axis}': None for s in ('left', 'right') for axis in ('x', 'y')}}
    if len(poses) != 1:
        return row, 'multiple_people' if poses else 'no_pose'
    row.update(measure(poses[0], width, height, threshold))
    ys = [p.y * height for p in poses[0] if visible(p, threshold)]
    if len(ys) >= 8:
        row['subject_height_pixels'] = round(max(ys) - min(ys), 2)
    return row, 'usable' if any(row[k] is not None for k in JOINTS) else 'low_confidence'


def landmark_record(points):
    # Missing model values stay null, rather than aborting the entire video or
    # writing invalid JSON NaN/Infinity literals.
    return [{key: float(v) if v is not None and math.isfinite(float(v)) else None
             for key in ('x', 'y', 'visibility', 'presence')
             for v in [getattr(p, key)]} for p in points]


def crop_filter(crop):
    """Percentages refer to the upright input before display-aspect scaling."""
    values = tuple(crop or (0, 0, 100, 100))
    if len(values) != 4 or any(isinstance(v, bool) or not math.isfinite(float(v)) for v in values):
        raise ValueError('裁剪需提供四个有限百分数：左、上、宽、高')
    left, top, width, height = map(float, values)
    if min(left, top) < 0 or min(width, height) < 5 or left + width > 100 or top + height > 100:
        raise ValueError('裁剪宽高至少 5%，且左 + 宽、上 + 高不能超过 100%')
    return f'crop=iw*{width/100}:ih*{height/100}:iw*{left/100}:ih*{top/100}'


def preview_region(filename, left=0, top=0, width=100, height=100):
    import cv2
    crop_filter((left, top, width, height))
    if not filename or not Path(filename).is_file():
        raise ValueError('请先上传录像')
    if Path(filename).stat().st_size > 500 * 1024 * 1024:
        raise ValueError('视频不能超过 500 MB')
    with tempfile.TemporaryDirectory(prefix='motion-preview-') as temporary:
        directory = Path(temporary)
        frame_path = directory / 'frame.png'
        run_ffmpeg(['-i', filename, '-map', '0:v:0', '-frames:v', '1', '-vf', DISPLAY_FILTER, frame_path], directory / 'process.log')
        frame = cv2.imread(str(frame_path))
        if frame is None:
            raise ValueError('无法读取视频第一帧')
        h, w = frame.shape[:2]
        a = (round(w * left / 100), round(h * top / 100))
        b = (min(w-1, round(w * (left + width) / 100)), min(h-1, round(h * (top + height) / 100)))
        cv2.rectangle(frame, a, b, (60, 225, 170), max(2, round(w / 240)))
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def summary_markdown(report):
    names = {'left_elbow': '左肘', 'right_elbow': '右肘', 'left_knee': '左膝', 'right_knee': '右膝',
             'left_hip': '左髋', 'right_hip': '右髋', 'torso_tilt': '躯干相对画面竖直的倾角'}
    lines = [f'### {SPORTS[report["sport"]]["name"]} · 姿态观察',
             f'处理 {report["processed_seconds"]:.2f} 秒；{report["usable_frames"]}/{report["sampled_frames"]} 帧有可用关节（{report["coverage"]:.0%}）。']
    if report['coverage'] < .5:
        lines += ['', '**有效检测不足 50%，请重新拍摄或调整阈值；不输出动作好坏或发力结论。**']
    lines += ['', *['**' + warning + '**' for warning in report.get('quality_warnings', [])]]
    lines += ['', '| 观察指标（二维） | 最小值 | 最大值 | 可用帧比例 |', '|---|---:|---:|---:|']
    for key in SPORTS[report['sport']]['focus']:
        stat = report['metrics'][key]
        low = '—' if stat['min'] is None else f'{stat["min"]:.1f}°'
        high = '—' if stat['max'] is None else f'{stat["max"]:.1f}°'
        lines.append(f'| {names[key]} | {low} | {high} | {stat["coverage"]:.0%} |')
    lines += ['', '**回看片段时关注**', ''] + ['- ' + x for x in SPORTS[report['sport']]['prompts']]
    timing = [e for e in report['keyframes'] if 'speed' in e.get('metric', '')]
    if timing:
        lines += ['', '**动作变化候选时刻（不是发力顺序判定）**', '']
        lines += [f'- {e["seconds"]:.2f} 秒：{e["title"]}。' for e in sorted(timing, key=lambda e: e['seconds'])]
    lines += ['', '这些是可回看的测量记录，不是力量测量或专业动作评分。']
    return '\n'.join(lines)


def _analyze(filename, threshold, sport, side, view, sample_fps, progress, crop=None):
    import cv2
    import mediapipe as mp
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    if not filename or not Path(filename).is_file():
        raise ValueError('请选择本地视频文件')
    source = Path(filename).resolve()
    if source.stat().st_size > 500 * 1024 * 1024:
        raise ValueError('视频不能超过 500 MB，请先剪辑成单次动作片段')
    if not math.isfinite(threshold) or not .3 <= threshold <= .95:
        raise ValueError('置信度阈值应在 0.3–0.95')
    if sport not in SPORTS or side not in {'left', 'right'} or view not in {'front', 'side', 'unknown'}:
        raise ValueError('请选择有效的运动、惯用侧和拍摄方向')
    if sample_fps not in {10, 15, 30}:
        raise ValueError('采样帧率应为 10、15 或 30')
    crop_expression = crop_filter(crop)
    cv2.setNumThreads(1)
    job = RUNS / uuid.uuid4().hex
    job.mkdir(parents=True)
    log = job / 'process.log'
    status_file = job / 'status.json'
    started = time.monotonic()
    status = {'status': 'running', 'job_id': job.name}
    def stage(desc, value):
        status['stage'] = desc
        status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
        if progress:
            progress(value, desc=desc)
    capture, writer = None, None
    try:
        stage('准备姿态模型', .02)
        model = model_file()
        stage('整理视频方向、尺寸与时间轴', .05)
        probe = cv2.VideoCapture(str(source))
        try:
            original_fps = float(probe.get(cv2.CAP_PROP_FPS))
            source_frames = float(probe.get(cv2.CAP_PROP_FRAME_COUNT))
        finally:
            probe.release()
        fps = min(float(sample_fps), original_fps) if math.isfinite(original_fps) and original_fps > 0 else float(sample_fps)
        if fps < 1:
            raise ValueError('视频帧率过低，无法观察动作时序')
        normalized = job / 'normalized.avi'
        raw_output = job / 'annotated_raw.avi'
        run_ffmpeg(['-i', source, '-map', '0:v:0', '-t', '60', '-vf',
                    f'{crop_expression},fps={fps},{DISPLAY_FILTER}',
                    '-an', '-c:v', 'mjpeg', '-q:v', '3', normalized], log)
        capture = cv2.VideoCapture(str(normalized))
        if not capture.isOpened():
            raise ValueError('无法读取预处理视频')
        frame_total = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model), delegate=mp.tasks.BaseOptions.Delegate.CPU),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=2,
            min_pose_detection_confidence=.5, min_tracking_confidence=.5)
        rows = []
        counts = {'no_pose': 0, 'multiple_people': 0, 'low_confidence': 0, 'usable': 0}
        width, height = 0, 0
        with (job / 'landmarks.jsonl').open('w', encoding='utf-8') as raw, mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            index = 0
            while index < math.ceil(60 * fps):
                ok, frame = capture.read()
                if not ok:
                    break
                height, width = frame.shape[:2]
                font_scale = max(.25, min(.6, width / 800))
                if writer is None:
                    writer = cv2.VideoWriter(str(raw_output), cv2.VideoWriter_fourcc(*'MJPG'), fps, (width, height))
                    if not writer.isOpened():
                        raise RuntimeError('无法创建视频编码器')
                seconds = index / fps
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
                detected = detector.detect_for_video(image, round(seconds * 1000))
                row, category = frame_observation(detected.pose_landmarks, seconds, width, height, threshold)
                counts[category] += 1
                if len(detected.pose_landmarks) == 1:
                    points = detected.pose_landmarks[0]
                    raw.write(json.dumps({'seconds': row['seconds'], 'landmarks': landmark_record(points)}, allow_nan=False) + '\n')
                    for a, b in EDGES:
                        if visible(points[a], threshold) and visible(points[b], threshold):
                            pa, pb = [(int(points[i].x * width), int(points[i].y * height)) for i in (a, b)]
                            cv2.line(frame, pa, pb, (70, 255, 194), 2)
                            cv2.circle(frame, pa, 4, (60, 225, 170), -1)
                elif len(detected.pose_landmarks) > 1:
                    cv2.putText(frame, 'Multiple poses; skipped', (8, 40), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (70, 180, 255), 1)
                else:
                    cv2.putText(frame, 'Pose unavailable', (8, 40), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (70, 180, 255), 1)
                label = f'{seconds:.2f}s | {sport} | 2D'
                cv2.putText(frame, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 3)
                cv2.putText(frame, label, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255), 1)
                writer.write(frame)
                rows.append(row)
                index += 1
                if index % max(1, int(fps)) == 0:
                    stage(f'分析动作 {seconds:.1f} 秒', .1 + .65 * min(1, index / frame_total))
        capture.release(); capture = None
        if writer is not None:
            writer.release(); writer = None
        if not rows:
            raise ValueError('视频没有可解码的帧')
        add_motion(rows, fps)
        stats, events = summarize(rows, sport, side, fps)
        subject_heights = [r['subject_height_pixels'] for r in rows if r['subject_height_pixels'] is not None]
        subject_height = median(subject_heights) if subject_heights else None
        quality_warnings = []
        if subject_height is not None and subject_height < 120:
            quality_warnings.append('人物像素高度不足 120，可能有明显关节抖动；已隐藏关键帧候选。请用更近、更清晰的全身录像。')
            events = []
        stage('生成关键帧和报告', .8)
        keyframes = []
        frames = cv2.VideoCapture(str(raw_output))
        try:
            for i, event in enumerate(events):
                frames.set(cv2.CAP_PROP_POS_FRAMES, event['frame_index'])
                ok, frame = frames.read()
                if ok:
                    path = job / f'keyframe_{i+1}.jpg'
                    if not cv2.imwrite(str(path), frame):
                        raise RuntimeError('保存关键帧失败')
                    keyframes.append((str(path), f'{event["title"]} · {event["seconds"]:.2f}s'))
        finally:
            frames.release()
        report = {'schema_version': 1, 'sport': sport, 'dominant_side': side, 'camera_view': view,
                  'status': 'measured' if counts['usable'] else 'no_usable_pose',
                  'sampled_frames': len(rows), 'usable_frames': counts['usable'],
                  'no_pose_frames': counts['no_pose'], 'multiple_person_frames': counts['multiple_people'],
                  'low_confidence_frames': counts['low_confidence'],
                  'coverage': round(counts['usable'] / len(rows), 3), 'sample_fps': fps,
                  'processed_seconds': round(len(rows) / fps, 3), 'source_fps_reported': original_fps if math.isfinite(original_fps) else None,
                  'input_duration_estimate': round(source_frames / original_fps, 3) if original_fps > 0 and math.isfinite(original_fps) and math.isfinite(source_frames) else None,
                  'frame_size': [width, height], 'threshold': threshold, 'metrics': stats, 'keyframes': events,
                  'subject_height_pixels_median': subject_height, 'quality_warnings': quality_warnings,
                  'force_estimated': False, 'time_basis': 'video_playback_seconds', 'model_sha256': hashlib.sha256(model.read_bytes()).hexdigest(),
                  'crop_percent': list(crop or (0, 0, 100, 100)),
                  'landmark_coordinate_space': 'cropped_upright_square_pixel_frame',
                  'limitations': LIMITATIONS, 'review_prompts': SPORTS[sport]['prompts']}
        with (job / 'measurements.csv').open('w', newline='', encoding='utf-8') as stream:
            csv_writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            csv_writer.writeheader(); csv_writer.writerows(rows)
        fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, facecolor='#0b100b')
        palette = ['#c2ff46', '#5ce1b8', '#e5efb0', '#8cb85b', '#74b6e8', '#f4bf78', '#b8a7ef']
        for ax in axes:
            ax.set_facecolor('#111810')
            ax.set_prop_cycle(color=palette)
            ax.tick_params(colors='#bdcbb2')
            ax.xaxis.label.set_color('#bdcbb2')
            ax.yaxis.label.set_color('#bdcbb2')
            ax.title.set_color('#edf3e9')
            for spine in ax.spines.values():
                spine.set_color('#34432b')
        times = [r['seconds'] for r in rows]
        for key in JOINTS:
            axes[0].plot(times, [r[key] if r[key] is not None else float('nan') for r in rows], label=key)
        axes[0].set(ylabel='Projected angle (degrees)', ylim=(0, 180), title='2D joint angles - gaps are missing detections')
        for side_name in ('left', 'right'):
            key = side_name + ('_knee_angular_speed_smoothed' if sport == 'skiing' else '_wrist_speed_smoothed')
            axes[1].plot(times, [r[key] if r[key] is not None else float('nan') for r in rows], label=side_name)
        axes[1].set(xlabel='Seconds', ylabel='degrees/s' if sport == 'skiing' else 'torso lengths/s', title='Observed motion rate (3-sample median)')
        for ax in axes:
            ax.legend(loc='best', facecolor='#172011', edgecolor='#34432b', labelcolor='#d5e3ca', fontsize=8)
            ax.grid(alpha=.15, color='#9ab580')
            ax.set_xlim(0, len(rows) / fps)
        fig.tight_layout(); fig.savefig(job / 'motion.png', dpi=140); plt.close(fig)
        stage('导出可播放视频', .9)
        output = job / 'annotated.mp4'
        run_ffmpeg(['-i', raw_output, '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart', output], log)
        normalized.unlink(missing_ok=True); raw_output.unlink(missing_ok=True)
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        (job / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        summary = summary_markdown(report)
        (job / 'summary.md').write_text(summary, encoding='utf-8')
        status['status'] = 'complete'
        stage('完成', 1)
        return str(output), str(job / 'motion.png'), keyframes, summary, report, [str(job / n) for n in ['measurements.csv', 'report.json', 'landmarks.jsonl', 'summary.md']]
    except Exception as exc:
        status.update(status='failed', error=str(exc), elapsed_seconds=round(time.monotonic() - started, 2))
        status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
        raise
    finally:
        if capture is not None:
            capture.release()
        if writer is not None:
            writer.release()


def analyze_video(filename, threshold=.65, sport='tennis', side='right', view='unknown', sample_fps=15, progress=None, crop=None):
    with analysis_lock():
        return _analyze(filename, threshold, sport, side, view, sample_fps, progress, crop)
