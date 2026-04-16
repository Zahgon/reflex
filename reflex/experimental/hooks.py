"""Add standard Hooks wrapper for React."""

from __future__ import annotations

from reflex_base.utils.imports import ImportVar
from reflex_base.vars import VarData
from reflex_base.vars.base import Var


def _compose_react_imports(tags: list[str]) -> dict[str, list[ImportVar]]:
    pass


def const(name: str | list[str], value: str | Var) -> Var:
    """Create a constant Var.

    Args:
        name: The name of the constant.
        value: The value of the constant.

    Returns:
        The constant Var.
    """
    pass


def useCallback(func: str, deps: list) -> Var:  # noqa: N802
    """Create a useCallback hook with a function and dependencies.

    Args:
        func: The function to wrap.
        deps: The dependencies of the function.

    Returns:
        The useCallback hook.
    """
    pass


def useContext(context: str) -> Var:  # noqa: N802
    """Create a useContext hook with a context.

    Args:
        context: The context to use.

    Returns:
        The useContext hook.
    """
    pass


def useRef(default: str) -> Var:  # noqa: N802
    """Create a useRef hook with a default value.

    Args:
        default: The default value of the ref.

    Returns:
        The useRef hook.
    """
    pass


def useState(var_name: str, default: str | None = None) -> Var:  # noqa: N802
    """Create a useState hook with a variable name and setter name.

    Args:
        var_name: The name of the variable.
        default: The default value of the variable.

    Returns:
        A useState hook.
    """
    pass
