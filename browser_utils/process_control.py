"""Process-level browser control helpers.

This module provides best-effort CPU suppression by freezing and resuming the
Camoufox browser process group with SIGSTOP/SIGCONT on Unix-like systems.
"""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

logger = logging.getLogger("AIStudioProxyServer")

_idle_freeze_task: Optional[asyncio.Task] = None


def _get_camoufox_pid() -> Optional[int]:
    try:
        from api_utils.server_state import state

        if getattr(state, "camoufox_pid", None):
            return int(state.camoufox_pid)
    except Exception:
        pass

    env_pid = os.environ.get("CAMOUFOX_PID")
    if env_pid:
        try:
            return int(env_pid)
        except ValueError:
            return None
    return None


def _signal_camoufox_process(sig: int) -> bool:
    pid = _get_camoufox_pid()
    if not pid:
        logger.debug("[CPU] Camoufox PID not available; skipping process signal.")
        return False

    if sys.platform == "win32":
        logger.warning(
            f"[CPU] Process freeze/resume is not supported on Windows (PID: {pid})."
        )
        return False

    try:
        if hasattr(os, "getpgid") and hasattr(os, "killpg"):
            pgid = os.getpgid(pid)
            os.killpg(pgid, sig)
            logger.info(
                f"[CPU] Sent signal {sig} to Camoufox process group (PGID: {pgid}, PID: {pid})."
            )
        else:
            os.kill(pid, sig)
            logger.info(f"[CPU] Sent signal {sig} to Camoufox process (PID: {pid}).")
        return True
    except ProcessLookupError:
        logger.info(f"[CPU] Camoufox process already exited (PID: {pid}).")
        return False
    except PermissionError as exc:
        logger.warning(f"[CPU] Permission denied signaling Camoufox (PID: {pid}): {exc}")
        return False
    except Exception as exc:
        logger.warning(f"[CPU] Failed to signal Camoufox (PID: {pid}): {exc}")
        return False


async def resume_camoufox_process(warmup_seconds: float = 0.2) -> bool:
    """Resume a frozen Camoufox process and give it a short warmup window."""
    cancel_camoufox_freeze()
    resumed = _signal_camoufox_process(signal.SIGCONT)
    if resumed and warmup_seconds > 0:
        await asyncio.sleep(warmup_seconds)
    return resumed


def freeze_camoufox_process() -> bool:
    """Freeze the Camoufox process group with SIGSTOP."""
    return _signal_camoufox_process(signal.SIGSTOP)


def cancel_camoufox_freeze() -> None:
    """Cancel any pending idle freeze task."""
    global _idle_freeze_task
    task = _idle_freeze_task
    if task and not task.done():
        task.cancel()
    _idle_freeze_task = None


async def _freeze_after_delay(delay_seconds: float) -> None:
    try:
        logger.info(f"[CPU] Idle timer started; freezing in {delay_seconds:.0f}s if no activity.")
        await asyncio.sleep(delay_seconds)
        logger.info("[CPU] Idle period elapsed; freezing Camoufox now.")
        freeze_camoufox_process()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.debug(f"[CPU] Idle freeze task failed: {exc}")


def schedule_camoufox_freeze(delay_seconds: float = 60.0) -> None:
    """Schedule freezing the Camoufox process after an idle delay."""
    global _idle_freeze_task

    if delay_seconds <= 0:
        freeze_camoufox_process()
        return

    cancel_camoufox_freeze()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("[CPU] No running loop; cannot schedule idle freeze.")
        return

    _idle_freeze_task = loop.create_task(_freeze_after_delay(delay_seconds))
    logger.info(f"[CPU] Scheduled Camoufox freeze in {delay_seconds:.0f}s.")


def set_camoufox_pid(pid: Optional[int]) -> None:
    """Store the current Camoufox PID in process-local state and env."""
    try:
        from api_utils.server_state import state

        state.camoufox_pid = int(pid) if pid else None
    except Exception:
        pass

    if pid:
        os.environ["CAMOUFOX_PID"] = str(int(pid))
    else:
        os.environ.pop("CAMOUFOX_PID", None)


def clear_camoufox_pid() -> None:
    """Clear the stored Camoufox PID."""
    set_camoufox_pid(None)
