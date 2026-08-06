"""P6: 自动录屏 (Playwright record_video_dir)。

按 docs/演示录屏脚本_3min.md 自动执行演示操作并录制真实视频。
输出: docs/demo_video/ (Playwright webm) + 转 mp4 (若 ffmpeg 可用)

运行: python tests/record_demo.py (需 UI 于 8509)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = ROOT / "docs" / "demo_video"

if sys.stdout and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://localhost:8510"


def main() -> int:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": 1280, "height": 900},
        )
        page = context.new_page()

        # 第1幕: 首页 (翻转卡 + 打字机)
        page.goto(BASE + "/", timeout=30000)
        page.wait_for_timeout(15000)
        time.sleep(15)
        # 悬停翻转卡
        for f in page.frames:
            card = f.query_selector(".fc")
            if card:
                box = card.bounding_box()
                if box:
                    page.mouse.move(box["x"]+box["width"]/2, box["y"]+box["height"]/2)
                    page.wait_for_timeout(8000)
                time.sleep(14)
                break

        # 第2幕: 点击预置热点
        page.locator("button:has-text('分析 低空经济')").first.click(timeout=10000)
        page.wait_for_timeout(12000)
        time.sleep(16)

        # 第3幕: Agent 轨迹 + 影响链
        page.wait_for_timeout(10000)
        time.sleep(16)

        # 第4幕: 因子/风险/报告
        page.locator("a", has_text="多因子分析").first.click(timeout=8000)
        page.wait_for_timeout(9000)
        page.locator("a", has_text="风险分析").first.click(timeout=8000)
        page.wait_for_timeout(9000)
        page.locator("a", has_text="研究报告").first.click(timeout=8000)
        page.wait_for_timeout(9000)

        # 第5幕: 深色切换
        try:
            page.locator("[data-testid='stSidebar']").hover()
            page.wait_for_timeout(1000)
        except Exception:
            pass

        # 第6幕: 结束 (补足 2:30)
        page.wait_for_timeout(8000)
        time.sleep(12)

        page.close()
        video_path = page.video.path() if page.video else None
        context.close()
        browser.close()

    elapsed = time.time() - t0
    print(f"录屏完成: {elapsed:.1f}s")
    print(f"视频: {video_path}")

    # 转 mp4 (ffmpeg 可用时)
    if video_path and Path(video_path).exists():
        try:
            import subprocess
            mp4 = VIDEO_DIR / "demo_video_final.mp4"
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", str(video_path), "-c:v", "libx264", "-crf", "23", str(mp4)],
                capture_output=True, timeout=120,
            )
            if r.returncode == 0 and mp4.exists():
                print(f"MP4 导出: {mp4} ({mp4.stat().st_size/1024/1024:.1f}MB)")
            else:
                print("ffmpeg 不可用或失败, 保留 webm")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"MP4 转码跳过: {str(e)[:60]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
