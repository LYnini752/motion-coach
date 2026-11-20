import os
from pathlib import Path

os.environ.setdefault('GRADIO_ANALYTICS_ENABLED', 'False')
import gradio as gr
from analysis import analyze_video, preview_region


CSS = Path(__file__).with_name('studio.css').read_text(encoding='utf-8')
EMPTY_SUMMARY = '### 等待一次新的观察\n上传录像并开始分析后，这里会显示检测覆盖率、关节角度和回看提示。'


def run(video, threshold, sport, side, view, fps, crop_left=0, crop_top=0, crop_width=100, crop_height=100, progress=gr.Progress()):
    try:
        return analyze_video(video, threshold, sport, side, view, int(fps), progress,
                             crop=(crop_left, crop_top, crop_width, crop_height))
    except Exception as exc:
        raise gr.Error(str(exc)) from None


def run_studio(*args, progress=gr.Progress()):
    result = run(*args, progress=progress)
    return (*result, gr.Tabs(selected='analysis'))


def preview(video, left, top, width, height):
    try:
        return preview_region(video, left, top, width, height)
    except Exception as exc:
        raise gr.Error(str(exc)) from None


def reset_clip(video):
    return video, None, None, [], EMPTY_SUMMARY, None, None, None, gr.Tabs(selected='source')


def build_app():
    theme = gr.themes.Base(primary_hue='lime', neutral_hue='zinc', font=['Inter', 'PingFang SC', 'system-ui', 'sans-serif']).set(
        body_background_fill='#080b09', body_background_fill_dark='#080b09',
        body_text_color='#edf3e9', body_text_color_dark='#edf3e9',
        block_background_fill='#111610', block_background_fill_dark='#111610',
        block_border_color='#2a3428', block_border_color_dark='#2a3428',
        block_label_text_color='#b3c0ab', block_label_text_color_dark='#b3c0ab',
        block_label_background_fill='#111610', block_label_background_fill_dark='#111610',
        block_title_text_color='#edf3e9', block_title_text_color_dark='#edf3e9',
        input_background_fill='#0b100b', input_background_fill_dark='#0b100b',
        input_border_color='#34402f', input_border_color_dark='#34402f',
        input_placeholder_color='#83917c', input_placeholder_color_dark='#83917c',
        button_primary_background_fill='#c2ff46', button_primary_background_fill_dark='#c2ff46',
        button_primary_background_fill_hover='#d4ff82', button_primary_background_fill_hover_dark='#d4ff82',
        button_primary_text_color='#101707', button_primary_text_color_dark='#101707',
        button_secondary_background_fill='#1b2417', button_secondary_background_fill_dark='#1b2417',
        button_secondary_text_color='#edf3e9', button_secondary_text_color_dark='#edf3e9',
        border_color_primary='#2a3428', border_color_primary_dark='#2a3428',
    )
    with gr.Blocks(title='Motion Coach · 运动姿态观察室', theme=theme, css=CSS, analytics_enabled=False) as demo:
        gr.HTML('''<header class="mc-nav"><div class="mc-brand"><span class="mc-mark">M<span>↗</span></span><span>MOTION<span class="mc-brand-light"> / COACH</span></span></div><div class="mc-mode"><i></i> 本机分析 <span class="mc-divider">/</span> 2D OBSERVER</div></header>
        <section class="mc-hero"><div><div class="mc-eyebrow">MOVE. REPLAY. UNDERSTAND.</div><h1>看清动作，<span>再进一步。</span></h1><p>从一次挥拍到一个转弯。逐帧回看身体轨迹，让每次练习有迹可循。</p></div><div class="mc-hero-side"><span class="mc-orbit">↗</span><span>网球 / 高尔夫 / 滑雪<br><b>YOUR MOVEMENT, IN FOCUS.</b></span></div></section>''')
        with gr.Row(equal_height=False, elem_id='mc-workspace'):
            with gr.Column(scale=3, min_width=300, elem_id='mc-controls'):
                gr.HTML('<div class="mc-section"><span>01 / SETUP</span><h2>准备你的片段</h2></div>')
                sport = gr.Radio([('网球', 'tennis'), ('高尔夫', 'golf'), ('滑雪', 'skiing')], value='tennis', label='选择运动', elem_id='mc-sport')
                video = gr.File(type='filepath', file_types=['video'], label='上传录像', elem_id='mc-upload')
                gr.Markdown('单人 · 固定机位 · 全身入镜  \n最多分析前 60 秒，文件不超过 500 MB。', elem_classes=['mc-hint'])
                side = gr.Radio([('右侧', 'right'), ('左侧', 'left')], value='right', label='惯用侧 · 网球 / 高尔夫')
                with gr.Accordion('拍摄与分析设置', open=False):
                    view = gr.Radio([('正面 / 背面', 'front'), ('侧面', 'side'), ('不确定', 'unknown')], value='unknown', label='拍摄方向', info='只记录方向，不自动校正透视。')
                    threshold = gr.Slider(.3, .95, value=.65, step=.05, label='关键点置信度')
                    fps = gr.Radio([10, 15, 30], value=15, label='分析帧率', info='快速挥拍可选 30，处理耗时更长。')
                    gr.Markdown('**人物区域** · 默认使用完整画面。裁剪时，请确保整个动作都在框内。')
                    with gr.Row():
                        crop_left = gr.Number(value=0, minimum=0, maximum=95, label='左边起点 %')
                        crop_top = gr.Number(value=0, minimum=0, maximum=95, label='上边起点 %')
                    with gr.Row():
                        crop_width = gr.Number(value=100, minimum=5, maximum=100, label='区域宽度 %')
                        crop_height = gr.Number(value=100, minimum=5, maximum=100, label='区域高度 %')
                    preview_button = gr.Button('预览人物区域', size='sm')
                    preview_image = gr.Image(label='首帧裁剪预览', interactive=False)
                    preview_button.click(preview, [video, crop_left, crop_top, crop_width, crop_height], preview_image)
                button = gr.Button('开始分析  ↗', variant='primary', elem_id='mc-start')
                gr.Markdown('首次分析需下载姿态模型。分析过程中请保持页面打开。', elem_classes=['mc-hint'])
            with gr.Column(scale=7, min_width=360, elem_id='mc-stage'):
                gr.HTML('<div class="mc-section mc-stage-heading"><div><span>02 / REPLAY</span><h2>你的动作，逐帧看清</h2></div><span class="mc-tag">VIDEO WORKSPACE</span></div>')
                with gr.Tabs(elem_id='mc-viewer') as viewer:
                    with gr.Tab('原始录像', id='source'):
                        source = gr.Video(label='上传后在这里预览原片', interactive=False, height=365, elem_id='mc-source')
                    with gr.Tab('骨架回放', id='analysis'):
                        output = gr.Video(label='分析后显示骨架视频 · 无音轨', interactive=False, height=365)
                gr.HTML('<div class="mc-caption"><span class="mc-line"></span> 单人姿态追踪 <span>二维关节角度 / 动作变化 / 关键帧</span></div>')
        gr.HTML('<div class="mc-section mc-results-heading"><span>03 / INSIGHTS</span><h2>从回放到观察</h2><p>先看检测质量，再看角度和变化。缺失的关键点不会被当成有效测量。</p></div>')
        with gr.Tabs(elem_id='mc-insights'):
            with gr.Tab('观察摘要'):
                summary = gr.Markdown(EMPTY_SUMMARY, elem_id='mc-summary')
            with gr.Tab('角度与变化'):
                chart = gr.Image(label='分析后显示角度与动作变化曲线', interactive=False)
            with gr.Tab('关键帧'):
                gallery = gr.Gallery(label='关键帧候选 · 请结合原片回看', columns=3, object_fit='contain')
            with gr.Tab('导出记录'):
                files = gr.File(file_count='multiple', label='下载数据与摘要', interactive=False)
                with gr.Accordion('完整测量记录', open=False):
                    report = gr.JSON(label='报告')
        gr.HTML('<footer class="mc-footer"><strong>观察动作，不替代教练。</strong><p>画面投影不等于真实力量、承重或伤病风险。请确认画面实际只有一人，模型可能漏检旁人。姿态在本机处理；依赖联网行为与数据保存说明见 README。</p><span>MOTION / COACH <b>SOFTWARE ALPHA · 2D</b></span></footer>')
        outputs = [output, chart, gallery, summary, report, files]
        video.change(reset_clip, video, [source, *outputs, preview_image, viewer], queue=False)
        button.click(run_studio, [video, threshold, sport, side, view, fps, crop_left, crop_top, crop_width, crop_height], [*outputs, viewer], concurrency_limit=1)
    return demo


if __name__ == '__main__':
    build_app().queue(max_size=4).launch(server_name='127.0.0.1', server_port=int(os.getenv('PORT', '7864')), share=False, max_file_size='500mb')
