"""Base classes for shared / linked states."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import TypeVar

from reflex_base.constants import ROUTER_DATA
from reflex_base.event import Event, get_hydrate_event
from reflex_base.utils import console
from reflex_base.utils.exceptions import ReflexRuntimeError
from typing_extensions import Self

from reflex.istate.manager.token import BaseStateToken
from reflex.state import BaseState, State, _override_base_method

UPDATE_OTHER_CLIENT_TASKS: set[asyncio.Task] = set()
LINKED_STATE = TypeVar("LINKED_STATE", bound="SharedStateBaseInternal")


def _log_update_client_errors(task: asyncio.Task):
    """Log errors from updating other clients.

    Args:
        task: The asyncio task to check for errors.
    """
    pass


def _do_update_other_tokens(
    affected_tokens: set[str],
    previous_dirty_vars: dict[str, set[str]],
    state_type: type[BaseState],
) -> list[asyncio.Task]:
    """Update other clients after a shared state update.

    Submit the updates in separate asyncio tasks to avoid deadlocking.

    Args:
        affected_tokens: The tokens to update.
        previous_dirty_vars: The dirty vars to apply to other clients.
        state_type: The type of the shared state.

    Returns:
        The list of asyncio tasks created to perform the updates.
    """
    pass


@contextlib.asynccontextmanager
async def _patch_state(
    original_state: BaseState, linked_state: BaseState, full_delta: bool = False
):
    """Patch the linked state into the original state's tree, restoring it afterward.

    Args:
        original_state: The original shared state.
        linked_state: The linked shared state.
        full_delta: If True, mark all Vars in linked_state dirty and resolve
            the delta from the root. This option is used when linking or unlinking
            to ensure that other computed vars in the tree pick up the newly
            linked/unlinked values.
    """
    if (original_parent_state := original_state.parent_state) is None:
        msg = "Cannot patch root state as linked state."
        raise ReflexRuntimeError(msg)

    state_name = original_state.get_name()
    original_parent_state.substates[state_name] = linked_state
    linked_parent_state = linked_state.parent_state
    linked_state.parent_state = original_parent_state
    try:
        if full_delta:
            linked_state.dirty_vars.update(linked_state.base_vars)
            linked_state.dirty_vars.update(linked_state.backend_vars)
            linked_state.dirty_vars.update(linked_state.computed_vars)
            linked_state._mark_dirty()
        # Apply the updates into the existing state tree for rehydrate.
        root_state = original_state._get_root_state()
        root_state.dirty_vars.add("router")
        root_state.dirty_vars.add(ROUTER_DATA)
        root_state._mark_dirty()
        await root_state._get_resolved_delta()
        yield
    finally:
        original_parent_state.substates[state_name] = original_state
        linked_state.parent_state = linked_parent_state


class SharedStateBaseInternal(State):
    """The private base state for all shared states."""

    _exit_stack: contextlib.AsyncExitStack | None = None
    _held_locks: dict[str, dict[type[BaseState], BaseState]] | None = None

    def __getstate__(self):
        """Override redis serialization to remove temporary fields.

        Returns:
            The state dictionary without temporary fields.
        """
        s = super().__getstate__()
        s.pop("_previous_dirty_vars", None)
        s.pop("_exit_stack", None)
        s.pop("_held_locks", None)
        return s

    @_override_base_method
    def _clean(self):
        """Override BaseState._clean to track the last set of dirty vars.

        This is necessary for applying dirty vars from one event to other linked states.
        """
        pass

    @_override_base_method
    def _mark_dirty(self):
        """Override BaseState._mark_dirty to avoid marking certain vars as dirty.

        Since these internal fields are not persisted to redis, they shouldn't cause the
        state to be considered dirty either.
        """
        self.dirty_vars.discard("_previous_dirty_vars")
        self.dirty_vars.discard("_exit_stack")
        self.dirty_vars.discard("_held_locks")
        # Only mark dirty if there are still dirty vars, or any substate is dirty
        if self.dirty_vars or any(
            substate.dirty_vars for substate in self.substates.values()
        ):
            super()._mark_dirty()

    def _rehydrate(self):
        """Get the events to rehydrate the state.

        Returns:
            The events to rehydrate the state (these should be returned/yielded).
        """
        return [
            Event(
                name=get_hydrate_event(self._get_root_state()),
            ),
            State.set_is_hydrated(True),
        ]

    async def _link_to(self, token: str) -> Self:
        """Link this shared state to a token.

        After linking, subsequent access to this shared state will affect the
        linked token's state, and cause changes to be propagated to all other
        clients linked to that token.

        Args:
            token: The token to link to (Cannot contain underscore characters).

        Returns:
            The newly linked state.

        Raises:
            ReflexRuntimeError: If linking fails or token is invalid.
        """
        pass

    async def _unlink(self):
        """Unlink this shared state from its linked token.

        Returns:
            The events to rehydrate the state after unlinking (these should be returned/yielded).
        """
        from reflex.istate.manager import get_state_manager

        if not isinstance(self, SharedState):
            msg = "Can only unlink SharedState instances."
            raise ReflexRuntimeError(msg)

        state_name = self.get_full_name()
        if (
            not self._reflex_internal_links
            or state_name not in self._reflex_internal_links
        ):
            msg = f"State {state_name} is not linked and cannot be unlinked."
            raise ReflexRuntimeError(msg)

        # Break the linkage for future events.
        self._reflex_internal_links.pop(state_name)
        self._linked_from.discard(self.router.session.client_token)

        # Patch in the original state, apply updates, then rehydrate.
        private_root_state = await get_state_manager().get_state(
            BaseStateToken(
                ident=self.router.session.client_token,
                cls=type(self),
            )
        )
        private_state = await private_root_state.get_state(type(self))
        async with _patch_state(
            original_state=self,
            linked_state=private_state,
            full_delta=True,
        ):
            return self._rehydrate()

    async def _internal_patch_linked_state(
        self, token: str, full_delta: bool = False
    ) -> Self:
        """Load and replace this state with the linked state for a given token.

        Must be called inside a `_modify_linked_states` context, to ensure locks are
        released after the event is done processing.

        Args:
            token: The token of the linked state.
            full_delta: If True, mark all Vars in linked_state dirty and resolve
                delta to update cached computed vars

        Returns:
            The state that was linked into the tree.
        """
        pass

    def _held_locks_linked_states(self) -> list["SharedState"]:
        """Get all linked states currently held by this state.

        Returns:
            The list of linked states currently held.
        """
        pass

    @contextlib.asynccontextmanager
    async def _modify_linked_states(
        self, previous_dirty_vars: dict[str, set[str]] | None = None
    ) -> AsyncIterator[None]:
        """Take lock, fetch all linked states, and patch them into the current state tree.

        If previous_dirty_vars is NOT provided, then any dirty vars after
        exiting the context will be applied to all other clients linked to this
        state's linked token.

        Args:
            previous_dirty_vars: When apply linked state changes to other
                tokens, provide mapping of state full_name to set of dirty vars.

        Yields:
            None.
        """
        pass


class SharedState(SharedStateBaseInternal, mixin=True):
    """Mixin for defining new shared states."""

    _linked_from: set[str] = set()
    _linked_to: str = ""
    _previous_dirty_vars: set[str] = set()

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Initialize subclass and set up shared state fields.

        Args:
            **kwargs: The kwargs to pass to the init_subclass method.
        """
        kwargs["mixin"] = False
        cls._mixin = False
        super().__init_subclass__(**kwargs)
        root_state = cls.get_root_state()
        if root_state.backend_vars["_reflex_internal_links"] is None:
            root_state.backend_vars["_reflex_internal_links"] = {}
        if root_state is State:
            # Always fetch SharedStateBaseInternal to access
            # `_modify_linked_states` without having to use `.get_state()` which
            # pulls in all linked states and substates which may not actually be
            # accessed for this event.
            root_state._always_dirty_substates.add(SharedStateBaseInternal.get_name())
