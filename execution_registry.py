# -*- coding: utf-8 -*-
"""Compatibility export for the Windows Agent execution registry API."""
from manager_client import (
    add_execution_event,
    get_execution_registry,
    register_execution,
    request_execution_stop,
    request_stop_all_executions,
    update_execution,
)

__all__ = [
    "add_execution_event",
    "get_execution_registry",
    "register_execution",
    "request_execution_stop",
    "request_stop_all_executions",
    "update_execution",
]
