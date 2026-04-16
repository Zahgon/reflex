"""A state manager that stores states on disk."""

import asyncio
import contextlib
import dataclasses
import functools
import time
from collections.abc import AsyncIterator
from hashlib import md5
from pathlib import Path
from typing import Any, Generic, cast

from reflex_base.environment import environment
from typing_extensions import Unpack, override

from reflex.istate.manager import (
    StateManager,
    StateModificationContext,
    _default_token_expiration,
)
from reflex.istate.manager.token import TOKEN_TYPE, BaseStateToken, StateToken
from reflex.state import BaseState
from reflex.utils import console, path_ops, prerequisites
from reflex.utils.misc import run_in_thread


@dataclasses.dataclass(frozen=True)
class QueueItem(Generic[TOKEN_TYPE]):
    """An item in the write queue."""

    token: StateToken[TOKEN_TYPE]
    state: TOKEN_TYPE
    timestamp: float


@dataclasses.dataclass
class StateManagerDisk(StateManager):
    """A state manager that stores states on disk."""

    # The mapping of client ids to states.
    states: dict[str, Any] = dataclasses.field(default_factory=dict)

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default=asyncio.Lock())

    # The dict of mutexes for each client
    _states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # The token expiration time (s).
    token_expiration: int = dataclasses.field(default_factory=_default_token_expiration)

    # Last time a token was touched.
    _token_last_touched: dict[str, float] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # Pending writes
    _write_queue: dict[StateToken, QueueItem] = dataclasses.field(
        default_factory=dict,
        init=False,
    )
    _write_queue_task: asyncio.Task | None = None
    _write_debounce_seconds: float = dataclasses.field(
        default=environment.REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS.get()
    )

    def __post_init__(self):
        """Create a new state manager."""
        path_ops.mkdir(self.states_directory)

        self._purge_expired_states()

    @functools.cached_property
    def states_directory(self) -> Path:
        """Get the states directory.

        Returns:
            The states directory.
        """
        pass

    def _purge_expired_states(self):
        """Purge expired states from the disk."""
        pass

    def token_path(self, token: StateToken) -> Path:
        """Get the path for a token.

        Args:
            token: The token to get the path for.

        Returns:
            The path for the token.
        """
        return (
            self.states_directory / f"{md5(str(token).encode()).hexdigest()}.pkl"
        ).absolute()

    async def load_state(self, token: StateToken[TOKEN_TYPE]) -> TOKEN_TYPE | None:
        """Load a state object based on the provided token.

        Args:
            token: The token used to identify the state object.

        Returns:
            The loaded state object or None.
        """
        token_path = self.token_path(token)

        if token_path.exists():
            try:
                with token_path.open(mode="rb") as file:
                    return token.deserialize(fp=file)
            except Exception:
                pass
        return None

    async def populate_substates(
        self, token: BaseStateToken, state: BaseState, root_state: BaseState
    ):
        """Populate the substates of a state object.

        Args:
            token: The token used to identify the state object.
            state: The state object to populate.
            root_state: The root state object.
        """
        for substate in state.get_substates():
            substate_token = token.with_cls(substate)

            fresh_instance = await root_state.get_state(substate)
            instance = await self.load_state(substate_token)
            if instance is not None:
                # Ensure all substates exist, even if they weren't serialized previously.
                instance.substates = fresh_instance.substates
            else:
                instance = fresh_instance
            state.substates[substate.get_name()] = instance
            instance.parent_state = state

            await self.populate_substates(token, instance, root_state)

    @override
    async def get_state(
        self,
        token: StateToken[TOKEN_TYPE],
    ) -> TOKEN_TYPE:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        token = self._coerce_token(token)
        root_state = self.states.get(token.cache_key)
        self._token_last_touched[token.cache_key] = time.time()
        if root_state is not None:
            # Retrieved state from memory.
            return root_state

        # Deserialize root state from disk.
        if isinstance(token, BaseStateToken):
            # Find the root state
            root_state_cls = token.cls.get_root_state()
            root_state = await self.load_state(token.with_cls(root_state_cls))
            # Create a new root state tree with all substates instantiated.
            fresh_root_state = root_state_cls(_reflex_internal_init=True)
            if root_state is None:
                root_state = fresh_root_state
            elif not isinstance(root_state, BaseState):
                msg = "Deserialized state is not an instance of BaseState, cannot populate substates."
                raise TypeError(msg)
            else:
                # Ensure all substates exist, even if they were not serialized previously.
                root_state.substates = fresh_root_state.substates
            await self.populate_substates(token, root_state, root_state)
            self.states[token.cache_key] = root_state
            return cast(TOKEN_TYPE, root_state)
        # For non-BaseState tokens, if the deserialized state is None, we create a new instance using the token's cls.
        state = await self.load_state(token)
        if state is None:
            state = token.cls()
        self.states[token.cache_key] = state
        return cast(TOKEN_TYPE, state)

    async def set_state_for_substate(
        self, token: StateToken[TOKEN_TYPE], substate: TOKEN_TYPE
    ):
        """Set the state for a substate.

        Args:
            token: The token used to identify the state object.
            substate: The substate to set.
        """
        pass

    async def _process_write_queue_delay(self):
        """Wait for the debounce period before processing the write queue again."""
        pass

    async def _process_write_queue(self):
        """Long running task that checks for states to write to disk.

        Raises:
            asyncio.CancelledError: When the task is cancelled.
        """
        pass

    async def _flush_write_queue(self):
        """Flush any remaining items in the write queue to disk."""
        pass

    async def _schedule_process_write_queue(self):
        """Schedule the write queue processing task if not already running."""
        pass

    @override
    async def set_state(
        self,
        token: StateToken[TOKEN_TYPE],
        state: TOKEN_TYPE,
        **context: Unpack[StateModificationContext],
    ):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
            context: The state modification context.
        """
        pass

    @override
    @contextlib.asynccontextmanager
    async def modify_state(
        self, token: StateToken[TOKEN_TYPE], **context: Unpack[StateModificationContext]
    ) -> AsyncIterator[TOKEN_TYPE]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.
            context: The state modification context.

        Yields:
            The state for the token.
        """
        pass

    async def close(self):
        """Close the state manager, flushing any pending writes to disk."""
        async with self._state_manager_lock:
            if self._write_queue_task:
                self._write_queue_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._write_queue_task
                    self._write_queue_task = None
            # Dump unlocked locks.
            for token, lock in tuple(self._states_locks.items()):
                if not lock.locked():
                    self._states_locks.pop(token)
