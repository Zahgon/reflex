"""Helper functions for adding assets to the app."""

import inspect
from pathlib import Path

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import EnvironmentVariables


def remove_stale_external_asset_symlinks():
    """Remove broken symlinks and empty directories in assets/external/.

    When a Python module directory that uses rx.asset(shared=True) is renamed
    or deleted, stale symlinks remain in assets/external/ pointing to the old
    path. This cleanup prevents issues with file watchers detecting symlink
    re-creation during import.
    """
    external_dir = (
        Path.cwd() / constants.Dirs.APP_ASSETS / constants.Dirs.EXTERNAL_APP_ASSETS
    )
    if not external_dir.exists():
        return

    # Remove broken symlinks.
    broken = [
        p
        for p in external_dir.rglob("*")
        if p.is_symlink() and not p.resolve().exists()
    ]
    for path in broken:
        path.unlink()

    # Remove empty directories left behind (deepest first).
    for dirpath in sorted(external_dir.rglob("*"), reverse=True):
        if dirpath.is_dir() and not dirpath.is_symlink() and not any(dirpath.iterdir()):
            dirpath.rmdir()


def asset(
    path: str,
    shared: bool = False,
    subfolder: str | None = None,
    _stack_level: int = 1,
) -> str:
    """Add an asset to the app, either shared as a symlink or local.

    Shared/External/Library assets:
        Place the file next to your including python file.
        Links the file to the app's external assets directory.

    Example:
    ```python
    # my_custom_javascript.js is a shared asset located next to the including python file.
    rx.script(src=rx.asset(path="my_custom_javascript.js", shared=True))
    rx.image(src=rx.asset(path="test_image.png", shared=True, subfolder="subfolder"))
    ```

    Local/Internal assets:
        Place the file in the app's assets/ directory.

    Example:
    ```python
    # local_image.png is an asset located in the app's assets/ directory. It cannot be shared when developing a library.
    rx.image(src=rx.asset(path="local_image.png"))
    ```

    Args:
        path: The relative path of the asset.
        subfolder: The directory to place the shared asset in.
        shared: Whether to expose the asset to other apps.
        _stack_level: The stack level to determine the calling file, defaults to
            the immediate caller 1. When using rx.asset via a helper function,
            increase this number for each helper function in the stack.

    Returns:
        The relative URL to the asset.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If subfolder is provided for local assets.
    """
    pass
