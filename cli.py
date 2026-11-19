import argparse
import json
from analysis import analyze_video, model_file, ffmpeg_path


def main():
    parser = argparse.ArgumentParser(description='Local 2D sports-pose observation')
    parser.add_argument('video', nargs='?')
    parser.add_argument('--sport', choices=['tennis', 'golf', 'skiing'], default='tennis')
    parser.add_argument('--side', choices=['left', 'right'], default='right')
    parser.add_argument('--view', choices=['front', 'side', 'unknown'], default='unknown')
    parser.add_argument('--fps', type=int, choices=[10, 15, 30], default=15)
    parser.add_argument('--threshold', type=float, default=.65)
    parser.add_argument('--crop', type=float, nargs=4, metavar=('LEFT', 'TOP', 'WIDTH', 'HEIGHT'),
                        help='Optional upright-frame crop in percent; full body must remain inside')
    parser.add_argument('--doctor', action='store_true', help='Download/check model and print runtime versions')
    args = parser.parse_args()
    if args.doctor:
        import cv2, mediapipe
        print(json.dumps({'model': str(model_file()), 'ffmpeg': ffmpeg_path(), 'opencv': cv2.__version__, 'mediapipe': mediapipe.__version__}, indent=2))
        return
    if not args.video:
        parser.error('video is required')
    try:
        result = analyze_video(args.video, args.threshold, args.sport, args.side, args.view, args.fps,
                               progress=lambda _, desc: print(desc, flush=True), crop=args.crop)
        print(result[3])
        print(json.dumps({'video': result[0], 'chart': result[1], 'files': result[5]}, ensure_ascii=False, indent=2))
    except Exception as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
