"""Middleware to hydrate the state."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from reflex_base import constants
from reflex_base.event import Event, get_hydrate_event

from reflex.middleware.middleware import Middleware
from reflex.state import BaseState, StateUpdate, _resolve_delta

if TYPE_CHECKING:
    from reflex.app import App


@dataclasses.dataclass(init=True)
class HydrateMiddleware(Middleware):
    """Middleware to handle initial app hydration."""

    async def preprocess(
        self, app: App, state: BaseState, event: Event
    ) -> StateUpdate | None:
        """Preprocess the event.

        Args:
            app: The app to apply the middleware to.
            state: The client state.
            event: The event to preprocess.

        Returns:
            An optional delta or list of state updates to return.
        """
        pass
