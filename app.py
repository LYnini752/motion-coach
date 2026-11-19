import os
os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')
import gradio as gr
from analysis import analyze_video, preview_region


def run(video, threshold, sport, side, view, fps, crop_left=0, crop_top=0, crop_width=100, crop_height=100, progress=gr.Progress()):
    try:
        return analyze_video(video, threshold, sport, side, view, int(fps), progress,
                             crop=(crop_left, crop_top, crop_width, crop_height))
    except Exception as exc:
        raise gr.Error(str(exc)) from None


def preview(video, left, top, width, height):
    try:
        return preview_region(video, left, top, width, height)
    except Exception as exc:
        raise gr.Error(str(exc)) from None


def build_app():
    with gr.Blocks(title='Motion Coach', theme=gr.themes.Soft(), analytics_enabled=False) as demo:
        gr.Markdown('# 运动姿态观察室\n上传一段视频，回看骨架、关节角度与动作变化。适合单人、固定机位、单次动作或短片段。请先确认画面实际只有一人，模型可能漏检旁人。')
        with gr.Row():
            sport = gr.Radio([('网球', 'tennis'), ('高尔夫', 'golf'), ('滑雪', 'skiing')], value='tennis', label='运动')
            side = gr.Radio([('右侧', 'right'), ('左侧', 'left')], value='right', label='惯用侧（网球 / 高尔夫）')
        video = gr.File(type='filepath', file_types=['video'], label='上传录像（最多分析前 60 秒，500 MB 以内）')
        with gr.Accordion('拍摄与分析设置', open=False):
            view = gr.Radio([('正面 / 背面', 'front'), ('侧面', 'side'), ('不确定', 'unknown')], value='unknown', label='拍摄方向（记录用途，不自动校正透视）')
            threshold = gr.Slider(.3, .95, value=.65, step=.05, label='关键点置信度阈值')
            fps = gr.Radio([10, 15, 30], value=15, label='分析帧率（快速挥拍建议选 30，处理更慢）')
            gr.Markdown('**可选：人物区域裁剪**。人物太小时可缩小范围，请确保整段录像中全身都在范围内。默认保留完整画面，以下数值均为画面百分比。')
            with gr.Row():
                crop_left = gr.Number(value=0, minimum=0, maximum=95, label='左边起点 %')
                crop_top = gr.Number(value=0, minimum=0, maximum=95, label='上边起点 %')
                crop_width = gr.Number(value=100, minimum=5, maximum=100, label='区域宽度 %')
                crop_height = gr.Number(value=100, minimum=5, maximum=100, label='区域高度 %')
            preview_button = gr.Button('预览人物区域')
            preview_image = gr.Image(label='第一帧 · 绿色框是分析范围（请同时检查后续动作没有出框）', interactive=False)
            preview_button.click(preview, [video, crop_left, crop_top, crop_width, crop_height], preview_image)
        button = gr.Button('分析动作', variant='primary')
        summary = gr.Markdown()
        with gr.Row():
            output = gr.Video(label='骨架视频（无音轨）')
            chart = gr.Image(label='角度与动作变化')
        gallery = gr.Gallery(label='关键帧候选 · 请结合原片回看', columns=3)
        with gr.Accordion('完整测量记录', open=False):
            report = gr.JSON(label='报告')
        files = gr.File(file_count='multiple', label='下载数据与摘要')
        gr.Markdown('角度和速度是画面投影的测量，不能直接代表力量、承重或伤病风险。姿态在本机处理；MediaPipe 依赖可能发送运行统计，详情见 README。结果保存在 `.local/runs/`。')
        button.click(run, [video, threshold, sport, side, view, fps, crop_left, crop_top, crop_width, crop_height], [output, chart, gallery, summary, report, files], concurrency_limit=1)
    return demo


if __name__ == '__main__':
    build_app().queue(max_size=4).launch(server_name='127.0.0.1', server_port=int(os.getenv('PORT', '7864')), share=False, max_file_size='500mb')
