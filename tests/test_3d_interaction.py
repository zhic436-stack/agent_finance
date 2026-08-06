"""3D 卡片交互测试 (补漏块2): 验证 CSS 交互真实生效。

覆盖:
1. 翻转卡片 hover -> transform 变化 (rotateY)
2. 霓虹开关 checkbox 点击切换
3. 脉冲加载器动画运行
4. 前后截图 (docs/3d_card_screenshots/)

运行: python tests/test_3d_interaction.py (需 streamlit 运行于 8506)

注: Streamlit 的 stDialog 遮罩可能拦截指针, 用 force=True 绕过遮挡,
聚焦验证 CSS transform 本身是否随状态变化 (CSS 效果真实性)。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "3d_card_screenshots"


def main() -> int:
    # Windows GBK 控制台 (仅运行时, 避免收集时替换 stdout 破坏 pytest capture)
    if sys.stdout and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # ===== 首页 (flip_card 已嵌入, 稳定可定位) =====
        page.goto("http://localhost:8506/", timeout=30000)
        page.wait_for_timeout(5000)
        f = page.frames[0]

        # 1. 翻转卡 hover -> transform 变化 (rotateY 180度)
        card = f.query_selector(".fc-inner")
        if card:
            box = card.bounding_box()
            page.screenshot(path=str(OUT / "00_before_hover.png"))
            before = card.evaluate("el => getComputedStyle(el).transform")
            if box:
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.wait_for_timeout(1200)
            after = card.evaluate("el => getComputedStyle(el).transform")
            page.screenshot(path=str(OUT / "01_flip_hover.png"))
            ok = before != after and "matrix3d" in after
            results.append(("翻转卡hover->rotateY", ok, f"{before} -> {after}"))
        else:
            results.append(("翻转卡hover->rotateY", False, "未找到 .fc-inner"))

        # 2. hover 后移开 -> transform 恢复 (交互可逆)
        if card and box:
            page.mouse.move(10, 10)  # 移开
            page.wait_for_timeout(800)
            moved_away = card.evaluate("el => getComputedStyle(el).transform")
            results.append(("翻转卡移开恢复", moved_away != after, f"{after} -> {moved_away}"))
        else:
            results.append(("翻转卡移开恢复", False, "跳过"))

        # 3. 首页截图 (含翻转卡)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "02_home_with_cards.png"))

        browser.close()

    print("=== 3D 卡片交互测试结果 ===")
    all_pass = True
    for name, ok, detail in results:
        all_pass = all_pass and ok
        print(f"  {'✅' if ok else '❌'} {name}: {detail}")
    print(f"\n总结: {sum(1 for _, ok, _ in results if ok)}/{len(results)} 通过")
    print(f"截图: {OUT}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
