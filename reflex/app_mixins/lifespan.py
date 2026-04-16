"""Mixin that allow tasks to run during the whole app lifespan."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import inspect
import time
from collections.abc import Callable, Coroutine

from reflex_base.utils import console
from reflex_base.utils.exceptions import InvalidLifespanTaskTypeError
from starlette.applications import Starlette

from .mixin import AppMixin


@dataclasses.dataclass
class LifespanMixin(AppMixin):
    """A Mixin that allow tasks to run during the whole app lifespan.

    Attributes:
        lifespan_tasks: Lifespan tasks that are planned to run.
    """

    lifespan_tasks: set[asyncio.Task | Callable] = dataclasses.field(
        default_factory=set
    )

    @contextlib.asynccontextmanager
    async def _run_lifespan_tasks(self, app: Starlette):
        pass

    def register_lifespan_task(self, task: Callable | asyncio.Task, **task_kwargs):
        """Register a task to run during the lifespan of the app.

        Args:
            task: The task to register.
            **task_kwargs: The kwargs of the task.

        Raises:
            InvalidLifespanTaskTypeError: If the task is a generator function.
        """
        pass
