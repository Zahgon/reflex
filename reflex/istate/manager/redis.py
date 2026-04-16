"""A state manager that stores states in redis."""

import asyncio
import contextlib
import dataclasses
import inspect
import os
import sys
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, TypedDict, cast

from redis import ResponseError
from redis.asyncio import Redis
from reflex_base.config import get_config
from reflex_base.environment import environment
from reflex_base.utils import console
from reflex_base.utils.exceptions import (
    InvalidLockWarningThresholdError,
    LockExpiredError,
    StateSchemaMismatchError,
)
from typing_extensions import Unpack, override

from reflex.istate.manager import (
    StateManager,
    StateModificationContext,
    _default_token_expiration,
)
from reflex.istate.manager.token import TOKEN_TYPE, BaseStateToken, StateToken
from reflex.state import BaseState
from reflex.utils.tasks import ensure_task


def _default_lock_expiration() -> int:
    """Get the default lock expiration time.

    Returns:
        The default lock expiration time.
    """
    pass


def _default_lock_warning_threshold() -> int:
    """Get the default lock warning threshold.

    Returns:
        The default lock warning threshold.
    """
    pass


def _default_oplock_hold_time_ms() -> int:
    """Get the default opportunistic lock hold time.

    Returns:
        The default opportunistic lock hold time.
    """
    pass


# The lock waiter task should subscribe to lock channel updates within this period.
LOCK_SUBSCRIBE_TASK_TIMEOUT = 2  # seconds


SMR = f"[SMR:{os.getpid()}]"
start = time.monotonic()


class RedisPubSubMessage(TypedDict):
    """A Redis Pub/Sub message."""

    type: str
    pattern: bytes | None
    channel: bytes
    data: bytes | int


class OplockFound(Exception):  # noqa: N818
    """Indicates that an opportunistic lock was found."""


@dataclasses.dataclass
class StateManagerRedis(StateManager):
    """A state manager that stores states in redis."""

    # The redis client to use.
    redis: Redis

    # The token expiration time (s).
    token_expiration: int = dataclasses.field(default_factory=_default_token_expiration)

    # The maximum time to hold a lock (ms).
    lock_expiration: int = dataclasses.field(default_factory=_default_lock_expiration)

    # The maximum time to hold a lock (ms) before warning.
    lock_warning_threshold: int = dataclasses.field(
        default_factory=_default_lock_warning_threshold
    )

    # How long to opportunistically hold the redis lock in milliseconds (must be less than the token expiration).
    oplock_hold_time_ms: int = dataclasses.field(
        default_factory=_default_oplock_hold_time_ms
    )

    # The keyspace subscription string when redis is waiting for lock to be released.
    _redis_notify_keyspace_events: str = dataclasses.field(
        default="K"  # Enable keyspace notifications (target a particular key)
        "$"  # For String commands (like setting keys)
        "s"  # For Set commands (SADD, SREM, etc)
        "g"  # For generic commands (DEL, EXPIRE, etc)
        "x"  # For expired events
        "e"  # For evicted events (i.e. maxmemory exceeded)
    )

    # These events indicate that a lock is no longer held.
    _redis_keyspace_lock_release_events: set[bytes] = dataclasses.field(
        default_factory=lambda: {
            b"del",
            b"expired",
            b"evicted",
        }
    )

    # Whether keyspace notifications have been enabled.
    _redis_notify_keyspace_events_enabled: bool = dataclasses.field(default=False)

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(
        default=asyncio.Lock(), init=False
    )

    # Whether to opportunistically hold locks for fast in-memory access.
    _oplock_enabled: bool = dataclasses.field(
        default_factory=environment.REFLEX_OPLOCK_ENABLED.get, init=False
    )

    # Cached states
    _cached_states: dict[str, Any] = dataclasses.field(default_factory=dict, init=False)
    _cached_states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict, init=False
    )

    # Local Leases (token -> flush task)
    _local_leases: dict[str, asyncio.Task] = dataclasses.field(
        default_factory=dict, init=False
    )
    # The unique ID for this state manager, the domain for _local_leases.
    _instance_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))

    # Lock waiters for redis per-token lock.
    _lock_waiters: dict[bytes, list[asyncio.Event]] = dataclasses.field(
        default_factory=dict,
        init=False,
    )
    _lock_updates_subscribed: asyncio.Event = dataclasses.field(
        default_factory=asyncio.Event,
        init=False,
    )
    _lock_task: asyncio.Task | None = dataclasses.field(default=None, init=False)

    # Whether debug prints are enabled.
    _debug_enabled: bool = dataclasses.field(
        default=environment.REFLEX_STATE_MANAGER_REDIS_DEBUG.get(),
        init=False,
    )

    def __post_init__(self):
        """Validate the lock warning threshold.

        Raises:
            InvalidLockWarningThresholdError: If the lock warning threshold is invalid.
        """
        if self.lock_warning_threshold >= (lock_expiration := self.lock_expiration):
            msg = f"The lock warning threshold({self.lock_warning_threshold}) must be less than the lock expiration time({lock_expiration})."
            raise InvalidLockWarningThresholdError(msg)
        if self._oplock_enabled and self.oplock_hold_time_ms >= lock_expiration:
            msg = f"The opportunistic lock hold time({self.oplock_hold_time_ms}) must be less than the lock expiration time({lock_expiration})."
            raise InvalidLockWarningThresholdError(msg)
        with contextlib.suppress(RuntimeError):
            asyncio.get_running_loop()  # Check if we're in an event loop.
            self._ensure_lock_task()

    def _get_required_state_classes(
        self,
        target_state_cls: type[BaseState],
        subclasses: bool = False,
        required_state_classes: set[type[BaseState]] | None = None,
    ) -> set[type[BaseState]]:
        """Recursively determine which states are required to fetch the target state.

        This will always include potentially dirty substates that depend on vars
        in the target_state_cls.

        Args:
            target_state_cls: The target state class being fetched.
            subclasses: Whether to include subclasses of the target state.
            required_state_classes: Recursive argument tracking state classes that have already been seen.

        Returns:
            The set of state classes required to fetch the target state.
        """
        if required_state_classes is None:
            required_state_classes = set()
        # Get the substates if requested.
        if subclasses:
            for substate in target_state_cls.get_substates():
                self._get_required_state_classes(
                    substate,
                    subclasses=True,
                    required_state_classes=required_state_classes,
                )
        if target_state_cls in required_state_classes:
            return required_state_classes
        required_state_classes.add(target_state_cls)

        # Get dependent substates.
        for pd_substates in target_state_cls._get_potentially_dirty_states():
            self._get_required_state_classes(
                pd_substates,
                subclasses=False,
                required_state_classes=required_state_classes,
            )

        # Get the parent state if it exists.
        if parent_state := target_state_cls.get_parent_state():
            self._get_required_state_classes(
                parent_state,
                subclasses=False,
                required_state_classes=required_state_classes,
            )
        return required_state_classes

    def _get_populated_states(
        self,
        target_state: BaseState,
        populated_states: dict[str, BaseState] | None = None,
    ) -> dict[str, BaseState]:
        """Recursively determine which states from target_state are already fetched.

        Args:
            target_state: The state to check for populated states.
            populated_states: Recursive argument tracking states seen in previous calls.

        Returns:
            A dictionary of state full name to state instance.
        """
        if populated_states is None:
            populated_states = {}
        if target_state.get_full_name() in populated_states:
            return populated_states
        populated_states[target_state.get_full_name()] = target_state
        for substate in target_state.substates.values():
            self._get_populated_states(substate, populated_states=populated_states)
        if target_state.parent_state is not None:
            self._get_populated_states(
                target_state.parent_state, populated_states=populated_states
            )
        return populated_states

    @override
    async def get_state(
        self,
        token: StateToken[TOKEN_TYPE],
        top_level: bool = True,
        for_state_instance: BaseState | None = None,
    ) -> TOKEN_TYPE:
        """Get the state for a token.

        Args:
            token: The token to get the state for.
            top_level: If true, return the top-level root state.
            for_state_instance: If provided, attach the requested states to this existing state tree.

        Returns:
            The state for the token.

        Raises:
            RuntimeError: when the parent state for a requested state was not fetched.
        """
        token = self._coerce_token(token)
        if not isinstance(token, BaseStateToken):
            # Non-BaseState token: simple single-key fetch.
            redis_data = await self.redis.get(str(token))
            if redis_data is not None:
                return token.deserialize(data=redis_data)
            return token.cls()

        requested_state_cls = token.cls

        # Determine which states we already have.
        flat_state_tree: dict[str, BaseState] = (
            self._get_populated_states(for_state_instance) if for_state_instance else {}
        )

        # Determine which states from the tree need to be fetched.
        required_state_classes = sorted(
            self._get_required_state_classes(requested_state_cls, subclasses=True)
            - {type(s) for s in flat_state_tree.values()},
            key=lambda x: x.get_full_name(),
        )

        redis_pipeline = self.redis.pipeline()
        for state_cls in required_state_classes:
            redis_pipeline.get(str(token.with_cls(state_cls)))

        for state_cls, redis_state in zip(
            required_state_classes,
            await redis_pipeline.execute(),
            strict=False,
        ):
            state = None

            if redis_state is not None:
                # Deserialize the substate.
                with contextlib.suppress(StateSchemaMismatchError):
                    state = BaseState._deserialize(data=redis_state)
            if state is None:
                # Key didn't exist or schema mismatch so create a new instance for this token.
                state = state_cls(
                    init_substates=False,
                    _reflex_internal_init=True,
                )
            flat_state_tree[state.get_full_name()] = state
            if state.get_parent_state() is not None:
                parent_state_name, _dot, state_name = state.get_full_name().rpartition(
                    "."
                )
                parent_state = flat_state_tree.get(parent_state_name)
                if parent_state is None:
                    msg = (
                        f"Parent state for {state.get_full_name()} was not found "
                        "in the state tree, but should have already been fetched. "
                        "This is a bug"
                    )
                    raise RuntimeError(msg)
                parent_state.substates[state_name] = state
                state.parent_state = parent_state

        # To retain compatibility with previous implementation, by default, we return
        # the top-level state which should always be fetched or already cached.
        if top_level:
            return cast(
                TOKEN_TYPE,
                flat_state_tree[requested_state_cls.get_root_state().get_full_name()],
            )
        return cast(TOKEN_TYPE, flat_state_tree[requested_state_cls.get_full_name()])

    @override
    async def set_state(
        self,
        token: StateToken[TOKEN_TYPE],
        state: TOKEN_TYPE,
        *,
        lock_id: bytes | None = None,
        **context: Unpack[StateModificationContext],
    ):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
            lock_id: If provided, the lock must be held with this value to set the state.
            context: The event context.

        Raises:
            LockExpiredError: If lock_id is provided and the lock for the token is not held by that ID.
            RuntimeError: If the state instance doesn't match the state name in the token.
        """
        pass

    @contextlib.asynccontextmanager
    async def _try_modify_state(
        self, token: StateToken[TOKEN_TYPE], **context: Unpack[StateModificationContext]
    ) -> AsyncIterator[TOKEN_TYPE | None]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.
            context: The state modification context.

        Yields:
            The state for the token or None if we couldn't get the lock.
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

    @contextlib.asynccontextmanager
    async def _get_state_cached(
        self, token: StateToken[TOKEN_TYPE]
    ) -> AsyncIterator[TOKEN_TYPE | None]:
        """Get the cached state for a token, while holding the local lease lock.

        Args:
            token: The token to get the cached state for.

        Yields:
            The cached state for the token, or None if not cached/uncachable.
        """
        pass

    def _notify_next_waiter(self, key: bytes):
        """Notify the next waiter for a given lock key.

        Args:
            key: The redis lock key.
        """
        pass

    async def _create_lease_break_task(
        self,
        token: StateToken[TOKEN_TYPE],
        lock_id: bytes,
        cleanup_ctx: contextlib.AsyncExitStack,
        **context: Unpack[StateModificationContext],
    ) -> asyncio.Task | None:
        """Create a background task to break the local lease after lock expiration.

        Args:
            token: The token to create the lease break task for.
            lock_id: The ID of the lock.
            cleanup_ctx: Enter this context while running the lease break task.
            context: The state modification context.

        Returns:
            The lease break task, or None when there is contention.
        """
        pass

    @staticmethod
    def _lock_key(token: StateToken[Any]) -> bytes:
        """Get the redis key for a token's lock.

        Args:
            token: The token to get the lock key for.

        Returns:
            The redis lock key for the token.
        """
        pass

    async def _try_extend_lock(self, lock_key: bytes) -> bool | None:
        """Extends the current lock for another lock_expiration period.

        Does not change ownership of the lock!

        Args:
            lock_key: The redis key for the lock.

        Returns:
            True if the lock was extended.
        """
        pass

    async def _try_get_lock(self, lock_key: bytes, lock_id: bytes) -> bool | None:
        """Try to get a redis lock for a token.

        Args:
            lock_key: The redis key for the lock.
            lock_id: The ID of the lock.

        Returns:
            True if the lock was obtained.
        """
        pass

    async def _handle_lock_release(self, message: RedisPubSubMessage) -> None:
        """Handle a lock release message from redis.

        Args:
            message: The redis message.
        """
        pass

    async def _handle_lock_contention(self, message: RedisPubSubMessage) -> None:
        """Handle a lock contention message from redis.

        Args:
            message: The redis message.
        """
        pass

    async def _subscribe_lock_updates(self):
        """Subscribe to redis keyspace notifications for lock updates."""
        pass

    def _ensure_lock_task(self) -> None:
        """Ensure the lock updates subscriber task is running."""
        pass

    async def _ensure_lock_task_subscribed(self, timeout: float | None = None) -> None:
        """Ensure the lock updates subscriber task is running and subscribed to avoid missing notifications.

        Args:
            timeout: How long to wait for the subscriber to be subscribed before
                raising an error. If None, defaults to
                min(LOCK_SUBSCRIBE_TASK_TIMEOUT, lock_expiration).

        Raises:
            TimeoutError: If the lock updates subscriber task fails to subscribe in time.
        """
        pass

    async def _enable_keyspace_notifications(self):
        """Enable keyspace notifications for the redis server.

        Raises:
            ResponseError: when the keyspace config cannot be set.
        """
        pass

    @contextlib.asynccontextmanager
    async def _lock_waiter(self, lock_key: bytes) -> AsyncIterator[asyncio.Event]:
        """Create a lock waiter for a given lock key.

        Args:
            lock_key: The redis key for the lock.

        Yields:
            The event that will be set when the lock is released.
        """
        pass

    def _n_lock_waiters(self, lock_key: bytes) -> int:
        """Get the number of local waiters for a given lock key.

        Args:
            lock_key: The redis key for the lock.

        Returns:
            The number of waiters for the lock key on this instance.
        """
        pass

    async def _n_lock_contenders(self, lock_key: bytes) -> int:
        """Get the number of contenders for a given lock key.

        Args:
            lock_key: The redis key for the lock.

        Returns:
            The number of contenders for the lock key across all instances.
        """
        pass

    @contextlib.asynccontextmanager
    async def _request_lock_release(
        self, lock_key: bytes, lock_id: bytes
    ) -> AsyncIterator[None]:
        """Request the release of a redis lock.

        Args:
            lock_key: The redis key for the lock.
            lock_id: The ID of the lock.
        """
        pass

    async def _get_local_lease(
        self, token: str, raise_when_found: bool = False
    ) -> asyncio.Task | None:
        """Check if there is a local lease for a token.

        Args:
            token: The token to check for a local lease.
            raise_when_found: If true, raise OplockFound when a local lease is found.

        Returns:
            The local lease task if found, None otherwise.

        Raises:
            OplockFound: If there is a local lease for the token and raise_when_found is True.
        """
        pass

    async def _wait_lock(self, lock_key: bytes, lock_id: bytes) -> None:
        """Wait for a redis lock to be released via pubsub.

        Coroutine will not return until the lock is obtained.

        It _might_ raise OplockFound if another coroutine in this process did
        get the lock and Oplock is enabled.

        Args:
            lock_key: The redis key for the lock.
            lock_id: The ID of the lock.
        """
        pass

    @contextlib.asynccontextmanager
    async def _lock(
        self, token: StateToken[Any], event_name: str | None = None
    ) -> AsyncIterator[bytes]:
        """Obtain a redis lock for a token.

        Args:
            token: The token to obtain a lock for.
            event_name: The name of the event associated with the lock.

        Yields:
            The ID of the lock (to be passed to set_state).

        Raises:
            LockExpiredError: If the lock has expired while processing the event.
        """
        pass

    async def close(self):
        """Explicitly close the redis connection and connection_pool.

        It is necessary in testing scenarios to close between asyncio test cases
        to avoid having lingering redis connections associated with event loops
        that will be closed (each test case uses its own event loop).

        Note: Connections will be automatically reopened when needed.
        """
        try:
            # Kill the lock task first so waiters don't get lock notifications.
            if self._lock_task is not None:
                self._lock_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._lock_task
                self._lock_task = None
            # Then cancel all outstanding leases and write the cached states to redis.
            for lease_task in self._local_leases.values():
                lease_task.cancel()
            await asyncio.gather(*self._local_leases.values(), return_exceptions=True)
        finally:
            await self.redis.aclose(close_connection_pool=True)
