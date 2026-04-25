"""Helpers for keeping the AI Studio tab active only when needed."""

import asyncio
import logging
from typing import Optional

from playwright.async_api import Error as PlaywrightAsyncError
from playwright.async_api import Page as AsyncPage

logger = logging.getLogger("AIStudioProxyServer")

_IDLE_TAB_URL = "about:blank"
_IDLE_RETURN_DELAY_SECONDS = 30.0
_idle_switch_task: Optional[asyncio.Task] = None
_idle_switch_generation: int = 0
_idle_switch_lock = asyncio.Lock()


async def prepare_idle_tab(work_page: AsyncPage) -> Optional[AsyncPage]:
    """Create or reuse a blank tab in the same browser context."""
    from api_utils.server_state import state

    if state.idle_page_instance and not state.idle_page_instance.is_closed():
        return state.idle_page_instance

    try:
        idle_page = await work_page.context.new_page()
        await idle_page.goto(_IDLE_TAB_URL, wait_until="domcontentloaded", timeout=10000)
        state.idle_page_instance = idle_page
        return idle_page
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.debug(f"[TabFocus] Failed to prepare idle tab: {e}")
        state.idle_page_instance = None
        return None


async def activate_work_page(work_page: AsyncPage) -> None:
    """Bring the AI Studio work page to the front and cancel any pending idle switch."""
    if not work_page or work_page.is_closed():
        return

    cancel_idle_switch()
    await prepare_idle_tab(work_page)

    try:
        await work_page.bring_to_front()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.debug(f"[TabFocus] Failed to bring work page to front: {e}")


def schedule_idle_switch(delay_seconds: float = _IDLE_RETURN_DELAY_SECONDS) -> None:
    """Schedule a delayed switch to the idle tab."""
    global _idle_switch_task, _idle_switch_generation

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    _idle_switch_generation += 1
    generation = _idle_switch_generation

    cancel_idle_switch()

    async def _delayed_switch() -> None:
        try:
            await asyncio.sleep(delay_seconds)
            async with _idle_switch_lock:
                if generation != _idle_switch_generation:
                    return

                from api_utils.server_state import state

                work_page = state.page_instance
                idle_page = state.idle_page_instance
                if (
                    not work_page
                    or work_page.is_closed()
                    or not idle_page
                    or idle_page.is_closed()
                ):
                    return

                await idle_page.bring_to_front()
        except asyncio.CancelledError:
            raise
        except PlaywrightAsyncError as e:
            logger.debug(f"[TabFocus] Idle switch Playwright error: {e}")
        except Exception as e:
            logger.debug(f"[TabFocus] Idle switch failed: {e}")

    _idle_switch_task = loop.create_task(_delayed_switch())


def cancel_idle_switch() -> None:
    """Cancel any scheduled idle switch."""
    global _idle_switch_task

    if _idle_switch_task and not _idle_switch_task.done():
        _idle_switch_task.cancel()


async def close_idle_tab() -> None:
    """Close the idle tab if one exists."""
    cancel_idle_switch()

    from api_utils.server_state import state

    idle_page = state.idle_page_instance
    state.idle_page_instance = None
    if idle_page and not idle_page.is_closed():
        try:
            await idle_page.close()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"[TabFocus] Failed to close idle tab: {e}")
