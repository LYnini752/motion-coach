# Validation

Recorded on 2026-11-19, macOS Apple Silicon, Python 3.13.3, MediaPipe 0.10.35, OpenCV 5.1.0.

## Verified

- Eleven lightweight tests cover aspect-ratio-correct geometry, out-of-frame/nonfinite observations, relative-coordinate translation invariance, time-based derivatives, missing-frame handling, sparse observations, sport-specific candidates and static-jitter suppression.
- Real MediaPipe VIDEO inference on a synthetic four-second fixture: 40 frames of Google's static pose example followed by 20 black frames. Result: exactly 60 output frames at 15 fps, 40 usable frames, 20 no-pose frames. The last 20 rows have empty joint values.
- A fully blank two-second video produced 30 no-pose frames, zero coverage and zero keyframe candidates. It returned an explicit no-usable-pose report, not an action evaluation.
- Actual FFmpeg normalization, OpenCV drawing, H.264 export, CSV/JSON/JSONL and chart generation completed. Intermediate video files were cleaned after successful export.
- Inspected the generated skeleton frame and chart. Corrected the chart to retain the entire processed time range, including missing detections at the end.
- Default model SHA-256: `59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a`.

- Clean isolated Python 3.13 environment installed successfully; 11 tests and doctor passed. A real Gradio client uploaded a rotation-metadata MP4 and received all six output types.
- Rotation metadata fixture produced an upright 480×640 result with 30/30 usable frames. A non-square-pixel (SAR=2) fixture normalized to 960×320 square pixels.
- Variable-frame-rate input was resampled to a fixed presentation-time timeline; the test produced 32 frames at 8.25688 fps (3.876 seconds). The container duration estimate was 3.633 seconds while the last decoded timestamp was 3.8 seconds; the estimate is not treated as ground-truth duration.
- A two-person composite exposed a detector limitation: only one pose was detected. This was **not** counted as successful multi-person exclusion. Documentation now makes the limitation explicit; the observed-multiple-poses branch is tested separately.
- A 65-second blank input was truncated to 600 frames / 60 seconds at 10 fps.
- Inspected desktop UI, region preview, skeleton output and charts. Added crop percentages with a first-frame preview; crop bounds and nonfinite values are validated.
- Real golf examples by [Nesnad, 2021](https://commons.wikimedia.org/wiki/File:Manpracticinggolfswing-slowmotion-2021-3-24.webm) and [Nesnad, 2023](https://commons.wikimedia.org/wiki/File:Golf_swing_practice_-_Kanagawa_-_slow_motion_-_2023_June_13.webm), available under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), were processed locally. The first had 146/513 usable frames uncropped and 477/513 after a 25/40/35/35 percent crop, but visible jitter remained. The new small-subject gate suppresses its keyframe candidates despite higher coverage. The second had 250/414 usable frames with substantial metric gaps. These results establish pipeline operation and limitations, **not reliable golf coaching**.

- Final Gradio API checks passed: region preview, cropped pose analysis with all six return values, and invalid-region error handling.
- MediaPipe 0.10.35 emitted a Clearcut upload-attempt log during the long blank fixture. No supported Python opt-out was verified. README discloses this dependency behavior; an exhaustive network/payload audit has not been performed.

## Still pending

- Tennis and skiing recordings, plus independently labeled golf key events; no accuracy, sports-coaching quality or biomechanical validation claim is made.
- Windows/Linux hardware verification.

A static-photo fixture verifies the pipeline and missing-data handling; it does not demonstrate dynamic sports tracking accuracy. The Google example image and derived test video stay local and are not redistributed.
