# 阻塞日志 (持续运行任务包)

## 阻塞1: ffmpeg 不可用
- 时间: 2026-08-01
- 现象: Playwright 录屏 webm 成功, MP4 转码失败 ([WinError 2] 系统找不到指定的文件)
- 影响: demo_video_auto.mp4 无法自动转码, 保留 webm
- 处理: 已跳过转码, webm 保留为证据; 用户本机装 ffmpeg 后可转
