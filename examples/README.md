# 高尔夫示例 / Golf sample

点“加载高尔夫示例”会填入视频、运动类型和裁剪参数，再点“开始分析”可本机重新运行。点“直接看示例结果”会显示已经跑过的骨架视频、图表和记录，无需模型下载或等待；摘要明确标注预计算结果。

来源：[Man practicing golf swing (slow motion)](https://commons.wikimedia.org/wiki/File:Manpracticinggolfswing-slowmotion-2021-3-24.webm)，Nesnad，2021-03-24。按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 使用。本例选择原文件的 CC BY 4.0 许可。作者不为本工具或结论背书。

原视频转为无音轨 H.264 / 15 fps；分析使用 25/40/35/35 百分比裁剪、10 fps 和 0.65 阈值。派生视频增加骨架，图表/表格为实际模型测量结果。未还原慢动作的真实时间。原始文件与派生数据的 SHA-256 见 `manifest.json`。原始文件来自之前合法下载的本机缓存，本轮重新核对了公开来源与许可证。

**样例展示真实限制：** 原片人物小，骨架会抖动，部分测量可能缺失；裁剪不能增加原片细节。不能据此测量真实挥杆速度、力量或判断动作优劣。网球与滑雪仍可上传自己的录像；本包只提供这段已核对许可的高尔夫视频。

## English

Use **加载高尔夫示例** to fill the video and preset, then start analysis. **直接看示例结果** displays precomputed real model outputs, explicitly labeled as such. No key or model download is needed for playback.

Credit: Nesnad, *Man practicing golf swing (slow motion)*, 2021-03-24, linked above, CC BY 4.0. Changes: silent H.264/15 fps transcode; derived outputs add skeleton overlays and measured charts, using the documented crop and 10 fps analysis. No endorsement is implied. Hashes and transformations are in `manifest.json`.

The original subject is small; jitter and missing observations are real limitations. Slow-motion playback time is not real-world movement time. This is a functional example, not a validated golf coaching result. Data and media keep CC BY 4.0; the repository's MIT license does not replace their license.
