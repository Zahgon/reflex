"""CLI for creating custom components."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import click
from reflex_base import constants
from reflex_base.constants import CustomComponents

from reflex.utils import console, frontend_skeleton


def _pyproject_toml_template(
    package_name: str, module_name: str, reflex_version: str
) -> str:
    """Template for custom components pyproject.toml.

    Args:
        package_name: The name of the package.
        module_name: The name of the module.
        reflex_version: The version of Reflex.

    Returns:
        Rendered pyproject.toml content as string.
    """
    pass


def _readme_template(module_name: str, package_name: str) -> str:
    """Template for custom components README.

    Args:
        module_name: The name of the module.
        package_name: The name of the package.

    Returns:
        Rendered README.md content as string.
    """
    pass


def _source_template(component_class_name: str, module_name: str) -> str:
    """Template for custom components source.

    Args:
        component_class_name: The name of the component class.
        module_name: The name of the module.

    Returns:
        Rendered custom component source code as string.
    """
    pass


def _init_template(module_name: str) -> str:
    """Template for custom components __init__.py.

    Args:
        module_name: The name of the module.

    Returns:
        Rendered __init__.py content as string.
    """
    pass


def _demo_app_template(custom_component_module_dir: str, module_name: str) -> str:
    """Template for custom components demo app.

    Args:
        custom_component_module_dir: The directory of the custom component module.
        module_name: The name of the module.

    Returns:
        Rendered demo app source code as string.
    """
    pass


def set_loglevel(ctx: Any, self: Any, value: str | None):
    """Set the log level.

    Args:
        ctx: The click context.
        self: The click command.
        value: The log level to set.
    """
    pass


@click.group
def custom_components_cli():
    """CLI for creating custom components."""


loglevel_option = click.option(
    "--loglevel",
    type=click.Choice(
        [loglevel.value for loglevel in constants.LogLevel],
        case_sensitive=False,
    ),
    callback=set_loglevel,
    is_eager=True,
    expose_value=False,
    help="The log level to use.",
)

POST_CUSTOM_COMPONENTS_GALLERY_TIMEOUT = 15


@contextmanager
def set_directory(working_directory: str | Path):
    """Context manager that sets the working directory.

    Args:
        working_directory: The working directory to change to.

    Yields:
        Yield to the caller to perform operations in the working directory.
    """
    pass


def _create_package_config(module_name: str, package_name: str):
    """Create a package config pyproject.toml file.

    Args:
        module_name: The name of the module.
        package_name: The name of the package typically constructed with `reflex-` prefix and a meaningful library name.
    """
    pass


def _create_readme(module_name: str, package_name: str):
    """Create a package README file.

    Args:
        module_name: The name of the module.
        package_name: The name of the python package to be published.
    """
    pass


def _write_source_and_init_py(
    custom_component_src_dir: Path,
    component_class_name: str,
    module_name: str,
):
    """Write the source code and init file from templates for the custom component.

    Args:
        custom_component_src_dir: The name of the custom component source directory.
        component_class_name: The name of the component class.
        module_name: The name of the module.
    """
    pass


def _populate_demo_app(name_variants: NameVariants):
    """Populate the demo app that imports the custom components.

    Args:
        name_variants: the tuple including various names such as package name, class name needed for the project.
    """
    pass


def _get_default_library_name_parts() -> list[str]:
    """Get the default library name. Based on the current directory name, remove any non-alphanumeric characters.

    Returns:
        The parts of default library name.

    Raises:
        SystemExit: If the current directory name is not suitable for python projects, and we cannot find a valid library name based off it.
    """
    pass


NameVariants = namedtuple(
    "NameVariants",
    [
        "library_name",
        "component_class_name",
        "package_name",
        "module_name",
        "custom_component_module_dir",
        "demo_app_dir",
        "demo_app_name",
    ],
)


def _validate_library_name(library_name: str | None) -> NameVariants:
    """Validate the library name.

    Args:
        library_name: The name of the library if picked otherwise None.

    Returns:
        A tuple containing the various names such as package name, class name, etc., needed for the project.

    Raises:
        SystemExit: If the library name is not suitable for python projects.
    """
    pass


def _populate_custom_component_project(name_variants: NameVariants):
    """Populate the custom component source directory. This includes the pyproject.toml, README.md, and the code template for the custom component.

    Args:
        name_variants: the tuple including various names such as package name, class name needed for the project.
    """
    pass


@custom_components_cli.command(name="init")
@click.option(
    "--library-name",
    default=None,
    help="The name of your library. On PyPI, package will be published as `reflex-{library-name}`.",
)
@click.option(
    "--install/--no-install",
    default=True,
    help="Whether to install package from this local custom component in editable mode.",
)
@loglevel_option
def init(
    library_name: str | None,
    install: bool,
):
    """Initialize a custom component.

    Args:
        library_name: The name of the library.
        install: Whether to install package from this local custom component in editable mode.

    Raises:
        SystemExit: If the pyproject.toml already exists.
    """
    pass


def _pip_install_on_demand(
    package_name: str,
    install_args: list[str] | None = None,
) -> bool:
    """Install a package on demand.

    Args:
        package_name: The name of the package.
        install_args: The additional arguments for the pip install command.

    Returns:
        True if the package is installed successfully, False otherwise.
    """
    pass


def _run_commands_in_subprocess(cmds: list[str]) -> bool:
    """Run commands in a subprocess.

    Args:
        cmds: The commands to run.

    Returns:
        True if the command runs successfully, False otherwise.
    """
    console.debug(f"Running command: {' '.join(cmds)}")
    try:
        result = subprocess.run(cmds, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as cpe:
        console.error(cpe.stdout)
        console.error(cpe.stderr)
        return False
    else:
        console.debug(result.stdout)
        return True


def _make_pyi_files():
    """Create pyi files for the custom component."""
    from reflex_base.utils.pyi_generator import PyiGenerator

    for top_level_dir in Path.cwd().iterdir():
        if not top_level_dir.is_dir() or top_level_dir.name.startswith("."):
            continue
        for dir, _, _ in top_level_dir.walk():
            if "__pycache__" in dir.name:
                continue
            PyiGenerator().scan_all([dir])


def _run_build():
    """Run the build command.

    Raises:
        SystemExit: If the build fails.
    """
    console.print("Building custom component...")

    _make_pyi_files()

    cmds = [sys.executable, "-m", "build", "."]
    if _run_commands_in_subprocess(cmds):
        console.info("Custom component built successfully!")
    else:
        raise SystemExit(1)


@custom_components_cli.command(name="build")
@loglevel_option
def build():
    """Build a custom component. Must be run from the project root directory where the pyproject.toml is."""
    _run_build()


def _collect_details_for_gallery():
    """Helper to collect details on the custom component to be included in the gallery.

    Raises:
        SystemExit: If pyproject.toml file is ill-formed or the request to the backend services fails.
    """
    pass


def _validate_url_with_protocol_prefix(url: str | None) -> bool:
    """Validate the URL with protocol prefix. Empty string is acceptable.

    Args:
        url: the URL string to check.

    Returns:
        Whether the entered URL is acceptable.
    """
    pass


def _get_file_from_prompt_in_loop() -> tuple[bytes, str] | None:
    pass


@custom_components_cli.command(name="share")
@loglevel_option
def share_more_detail():
    """Collect more details on the published package for gallery."""
    pass


@custom_components_cli.command(name="install")
@loglevel_option
def install():
    """Install package from this local custom component in editable mode.

    Raises:
        SystemExit: If unable to install the current directory in editable mode.
    """
    pass
