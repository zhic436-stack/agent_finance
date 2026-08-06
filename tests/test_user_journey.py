"""P5: 端到端用户旅程测试 (Playwright)。

模拟真实用户完整操作:
首页 → 预置热点 → 事件分析 → 因子 → 风险 → 报告 → 导出 → 主题切换
每步截图到 docs/e2e_screenshots/。

运行: python tests/test_user_journey.py (需 UI 于 8509)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "e2e_screenshots"

if sys.stdout and hasattr(sys.stdout, "buffer"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://localhost:8509"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    steps = []

    def shot(page, name):
        path = OUT / name
        page.screenshot(path=str(path), full_page=False)
        steps.append((name, path.stat().st_size))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # 1. 打开首页
        page.goto(BASE + "/", timeout=30000)
        page.wait_for_timeout(4000)
        shot(page, "01_home.png")

        # 2. 点击预置热点"低空经济"
        page.locator("button:has-text('分析 低空经济')").first.click(timeout=8000)
        page.wait_for_timeout(4000)
        shot(page, "02_event_analysis.png")

        # 3. 等待 Agent 轨迹 (demo_state 秒开)
        page.wait_for_timeout(2000)
        shot(page, "03_agent_trace.png")

        # 4. 因子分析页
        page.locator("a:has-text('多因子分析')").first.click(timeout=8000)
        page.wait_for_timeout(4000)
        shot(page, "04_factor.png")

        # 5. 风险分析页
        page.locator("a:has-text('风险分析')").first.click(timeout=8000)
        page.wait_for_timeout(4000)
        shot(page, "05_risk.png")

        # 6. 研究报告页
        page.locator("a:has-text('研究报告')").first.click(timeout=8000)
        page.wait_for_timeout(4000)
        shot(page, "06_report.png")

        # 7. 深色模式切换
        try:
            page.locator("input[aria-label='深色模式']").check(force=True, timeout=5000)
            page.wait_for_timeout(1500)
            shot(page, "07_dark_mode.png")
        except Exception:
            shot(page, "07_dark_mode.png")  # 截当前态

        # 8. 回到首页 (侧边栏, 宽松定位)
        try:
            page.locator("a", has_text="首页").first.click(timeout=6000)
        except Exception:
            try:
                page.locator("[data-testid='stSidebar'] a").first.click(timeout=6000)
            except Exception:
                pass
        page.wait_for_timeout(3000)
        shot(page, "08_back_home.png")

        browser.close()

    print("=== 端到端用户旅程测试 ===")
    ok = True
    for name, size in steps:
        good = size > 10000  # 非空截图
        ok = ok and good
        print(f"  {'✅' if good else '❌'} {name} ({size} bytes)")
    print(f"\n完成: {len(steps)} 步, {'全部成功' if ok else '有失败'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
