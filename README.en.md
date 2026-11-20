# Motion Coach

[简体中文](README.md) | [English](README.en.md)

Analyze a video locally and export a **skeleton overlay, 2D joint angles, motion curves, candidate keyframes, and measurement data** using MediaPipe Pose Landmarker. Choose tennis, golf, or skiing.

**Software alpha for observable 2D motion.** It does not estimate actual force, foot pressure, ski loading, injury risk, or professional technique scores from an ordinary video. Sport selection is manual; the app does not automatically identify sports, track rackets/clubs/balls/skis, or detect impact time. Image-space timing does not establish a biomechanical force sequence.

## What each mode shows

| Sport | Measurements of interest | Candidate keyframes |
|---|---|---|
| Tennis | Elbow angle, torso inclination, dominant-side relative wrist motion | Wrist-motion peak and about 0.3 seconds either side; knee angular-change peak |
| Golf | Elbow/hip angles and projected torso changes | Wrist and knee-change peaks; joint-angle extrema |
| Skiing | Left/right knee angles and their timing; torso projection | Minimum knee angles and knee angular-change peaks |

## Install and run

Requires Python 3.11–3.13. Model/video processing has been exercised on macOS Apple Silicon; see [VALIDATION.md](VALIDATION.md) for platform status, real-video results, and failures. That document is currently in Chinese. Installer/file-lock behavior targets macOS/Linux; native Windows is unverified.

```bash
git clone https://github.com/LYnini752/motion-coach.git
cd motion-coach
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python cli.py --doctor
python app.py
```

Open **http://127.0.0.1:7864**, upload a video, choose the sport and dominant side, then click **分析动作** (Analyze motion). Review the annotated video, plots, coverage warnings, and downloadable results. The UI and generated text summary currently use Chinese; this English README does not imply a translated UI.

The first analysis downloads a roughly 5.5 MB model from Google and verifies a pinned SHA-256. Once cached, analysis can run offline; see the dependency-network caveat below.

```bash
python cli.py '/path/to/tennis.mp4' --sport tennis --side right --fps 30
python cli.py '/path/to/golf.mov' --sport golf --view side
python cli.py '/path/to/skiing.mp4' --sport skiing --fps 15
```

`PORT` overrides the web port. `POSE_MODEL_PATH` supplies a compatible `.task` model. `FFMPEG_BINARY` overrides FFmpeg; otherwise the system binary or imageio-ffmpeg binary is used.

## Framing and cropping

Use a fixed camera and a clear, uncut, full-body video of one person. Frames where multiple people are detected are skipped, but the detector can miss other people: check the source yourself. There is no identity tracking or face recognition.

- Maximum file size: **500 MB**. Only the first **60 seconds** are analyzed.
- Prefer one swing or short skiing sequence per clip.
- Default sampling is 15 fps; select 30 fps for fast movement. Resampling cannot recover information absent from low-frame-rate footage.
- Slow-motion/speed-adjusted video is measured on its playback timeline; original motion speed is not reconstructed.
- Compare recordings from the same camera position, lens, and distance. These are projected 2D angles, not calibrated 3D angles.
- Higher confidence thresholds reduce uncertain measurements but increase missing values. Below 50% detection coverage, the report requests improved footage/settings.

For a small subject, expand **拍摄与分析设置** (Capture and analysis settings), enter left/top/width/height percentages, then choose **预览人物区域** (Preview subject region). Check that the whole body remains inside the crop throughout the clip. Cropping focuses the detector but cannot restore missing detail.

```bash
python cli.py video.mp4 --sport golf --crop 25 40 35 35
```

This selects horizontal 25–60% and vertical 40–75%. Coordinates refer to the cropped image after rotation and pixel-aspect correction. Full-frame analysis is the default. FFmpeg normalizes rotation, pixel aspect, and frame rate; output has a maximum long edge of 960 pixels, uses H.264 MP4, and omits audio.

## How to interpret measurements

1. MediaPipe supplies 33 landmarks. Only 2D coordinates, visibility, and presence confidence are used.
2. Coordinates are converted to pixels using actual width and height before computing elbow, knee, and hip angles.
3. Torso inclination is relative to image vertical; its sign means image left/right, not automatically forward/backward lean.
4. Wrist motion is relative to the hip center and normalized by projected torso length. Velocity is in **torso lengths/second**, not meters/second or racket speed.
5. Knee angular change is in degrees/second. Velocity uses a three-sample median; missing values remain missing and are not interpolated across occlusions.
6. Keyframe candidates need at least 50% usable samples and five valid frames for their metric. Wrist peaks require a 10th–90th percentile position range of at least 0.1 torso lengths; knee-change peaks require a 5-degree angle range to suppress static jitter.
7. All candidate keyframes are hidden when the median visible-landmark bounding-box height is below 120 pixels. These are conservative, uncalibrated display rules, not coaching or medical thresholds; larger subjects can still be tracked incorrectly.

Projected shoulder/hip line angles are saved but are not a true rotation measurement or golf X-factor. No joint torques or actual force estimates are computed without calibration, body mass, and external-force measurements.

## Outputs and privacy

Results are stored in `.local/runs/<run-id>/`:

- `annotated.mp4`: skeleton video; `motion.png`: measurement curves.
- `keyframe_*.jpg`: candidate frames to compare with the source.
- `report.json`: measurements, coverage, model hash, methods, and limitations.
- `measurements.csv`: per-frame values; blank cells mean missing, not zero.
- `landmarks.jsonl`: 2D landmarks from single-person detections.
- `summary.md`: Chinese summary; `status.json` and `process.log`: status/logs.

The app uses local inference, binds its UI to loopback, and disables Gradio analytics. Installation/model downloads need internet access. **MediaPipe 0.10.35 was observed attempting Clearcut telemetry**, also discussed in the [upstream issue](https://github.com/google-ai-edge/mediapipe/issues/6291). Payloads and a supported disable switch have not been fully established; this project does not promise zero network activity from dependencies. For strict offline use, download dependencies/models first, then run without external network access.

Uploaded files may remain in system temporary storage. Results are not automatically removed; delete unwanted run folders after use. Models and personal videos are excluded from Git.

## Development and license

```bash
python -m pip install pytest
python -m pytest -q
```

Lightweight CI covers geometry, time differences, missing values, jitter suppression, and mode differences. It does not replace real-video evaluation or professional coaching validation.

Project code is MIT. MediaPipe is Apache-2.0; models come from the [official Pose Landmarker documentation](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker?tab=Python). Dependencies/models retain their respective licenses. The HD default sample is CC0; the credited FOX Sports excerpt retains CC BY 3.0. See examples/README.md for attribution and edits. Other developer test photographs are not distributed.

## Interface

The black-and-neon-green studio places upload/settings on the left and source/skeleton playback on the right. Result tabs separate observations, angle charts, keyframes, and exports. Loading a new clip clears previous results; successful analysis opens skeleton playback. Charts and skeleton overlays follow the same palette. No unvalidated movement or force score is shown.

## Included samples

See [sample data and attribution](examples/README.md) for ready-to-use inputs, offline previews, licenses, and limitations. No API credentials are included.
