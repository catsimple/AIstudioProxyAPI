import asyncio
import random
import math
from typing import Optional
from python_ghost_cursor.shared._spoof import path, get_random_box_point
from python_ghost_cursor.shared._math import Vector


async def _get_current_mouse_pos(page) -> Optional[Vector]:
    try:
        result = await page.evaluate("""
            () => {
                if (window.__mouseTrackerInstalled && window.__mouseX !== undefined) {
                    return { x: window.__mouseX, y: window.__mouseY };
                }
                return null;
            }
        """)
        if result and isinstance(result, dict) and "x" in result:
            return Vector(float(result["x"]), float(result["y"]))
    except Exception:
        pass
    return None


async def _get_default_start_pos(page) -> Vector:
    try:
        viewport = await page.evaluate("""
            () => ({
                width: window.innerWidth || document.documentElement.clientWidth,
                height: window.innerHeight || document.documentElement.clientHeight,
            })
        """)
        vw = viewport.get("width", 1920)
        vh = viewport.get("height", 1080)
    except Exception:
        vw, vh = 1920, 1080
    x = vw * 0.5 + random.uniform(-100, 100)
    y = vh * 0.65 + random.uniform(-80, 80)
    return Vector(x, y)


async def _ensure_mouse_tracker(page):
    await page.evaluate("""
        () => {
            if (!window.__mouseTrackerInstalled) {
                window.__mouseTrackerInstalled = true;
                window.__mouseX = 0;
                window.__mouseY = 0;
                document.addEventListener('mousemove', (e) => {
                    window.__mouseX = e.clientX;
                    window.__mouseY = e.clientY;
                }, { capture: true });
            }
        }
    """)


async def human_move(
    page,
    target_selector: str,
    duration: float = 0.5,
    start_pos: Optional[Vector] = None,
) -> Vector:
    if start_pos is None:
        current = await _get_current_mouse_pos(page)
        start_pos = current if current is not None else await _get_default_start_pos(page)

    elem = await page.query_selector(target_selector)
    if elem is None:
        raise Exception(f"Element not found: {target_selector}")
    await elem.scroll_into_view_if_needed()
    box = await elem.bounding_box()
    if box is None:
        raise Exception(f"Cannot get bounding box for: {target_selector}")

    destination = get_random_box_point(box)
    vectors = path(start_pos, destination)

    if len(vectors) < 2:
        await page.mouse.move(destination.x, destination.y)
        return destination

    step_delay = duration / (len(vectors) - 1)

    for i, v in enumerate(vectors):
        await page.mouse.move(v.x, v.y)
        if i < len(vectors) - 1:
            await asyncio.sleep(step_delay)

    return destination


async def human_click(
    page,
    target_selector: str,
    move_duration: float = 0.5,
    start_pos: Optional[Vector] = None,
) -> Vector:
    await _ensure_mouse_tracker(page)
    if start_pos is None:
        current = await _get_current_mouse_pos(page)
        start_pos = current if current is not None else await _get_default_start_pos(page)

    destination = await human_move(page, target_selector, move_duration, start_pos)
    await asyncio.sleep(random.uniform(0.05, 0.10))
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.03, 0.06))
    await page.mouse.up()
    return destination
