"""
FastAPI 依赖项模块
"""

import logging
from asyncio import Event, Lock, Queue, Task
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, cast

from api_utils.context_types import QueueItem, ServerStateSnapshot

if TYPE_CHECKING:
    from playwright.async_api import Page as AsyncPage

    from models.logging import WebSocketConnectionManager


def get_logger() -> logging.Logger:
    from server import logger

    return logger


def get_log_ws_manager() -> Optional["WebSocketConnectionManager"]:
    from server import log_ws_manager

    return cast(Optional["WebSocketConnectionManager"], log_ws_manager)


def get_request_queue() -> "Queue[QueueItem]":
    from server import request_queue

    queue_obj = cast(Optional["Queue[QueueItem]"], request_queue)
    if queue_obj is None:
        raise RuntimeError("request_queue is not initialized")
    return queue_obj


def get_processing_lock() -> Lock:
    from server import processing_lock

    lock_obj = cast(Optional[Lock], processing_lock)
    if lock_obj is None:
        raise RuntimeError("processing_lock is not initialized")
    return lock_obj


def get_worker_task() -> Optional[Task[None]]:
    from server import worker_task

    return cast(Optional[Task[None]], worker_task)


def get_server_state() -> ServerStateSnapshot:
    from server import (
        is_browser_connected,
        is_initializing,
        is_page_ready,
        is_playwright_ready,
    )

    # 返回不可变快照，避免下游修改全局引用
    return cast(
        ServerStateSnapshot,
        {
            "is_initializing": is_initializing,
            "is_playwright_ready": is_playwright_ready,
            "is_browser_connected": is_browser_connected,
            "is_page_ready": is_page_ready,
        },
    )


def get_page_instance() -> Optional["AsyncPage"]:
    from server import page_instance

    return cast(Optional["AsyncPage"], page_instance)


def get_model_list_fetch_event() -> Event:
    from server import model_list_fetch_event

    return cast(Event, model_list_fetch_event)


def get_parsed_model_list() -> List[Dict[str, Any]]:
    from server import parsed_model_list

    return cast(List[Dict[str, Any]], parsed_model_list)


def get_excluded_model_ids() -> Set[str]:
    from server import excluded_model_ids

    return cast(Set[str], excluded_model_ids)


def get_current_ai_studio_model_id() -> Optional[str]:
    from server import current_ai_studio_model_id

    return cast(Optional[str], current_ai_studio_model_id)
