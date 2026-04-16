"""This module contains the dataclasses representing the router object."""

import dataclasses
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING
from urllib.parse import _NetlocResultMixinStr, parse_qsl, urlsplit

from reflex_base import constants
from reflex_base.utils import console, format
from reflex_base.utils.serializers import serializer


@dataclasses.dataclass(frozen=True, init=False)
class _FrozenDictStrStr(Mapping[str, str]):
    _data: MappingProxyType[str, str]

    def __init__(self, **kwargs):
        object.__setattr__(
            self, "_data", MappingProxyType(dict(sorted(kwargs.items())))
        )

    def __getitem__(self, key: str) -> str:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __hash__(self) -> int:
        return hash(frozenset(self._data.items()))

    def __getstate__(self) -> object:
        return dict(self._data)

    def __setstate__(self, state: object) -> None:
        if not isinstance(state, dict):
            msg = "Invalid state for _FrozenDictStrStr"
            raise TypeError(msg)
        object.__setattr__(self, "_data", MappingProxyType(state))


@dataclasses.dataclass(frozen=True)
class _HeaderData:
    host: str = ""
    origin: str = ""
    upgrade: str = ""
    connection: str = ""
    cookie: str = ""
    pragma: str = ""
    cache_control: str = ""
    user_agent: str = ""
    sec_websocket_version: str = ""
    sec_websocket_key: str = ""
    sec_websocket_extensions: str = ""
    accept_encoding: str = ""
    accept_language: str = ""
    raw_headers: Mapping[str, str] = dataclasses.field(
        default_factory=_FrozenDictStrStr
    )


_HEADER_DATA_FIELDS = frozenset([
    field.name for field in dataclasses.fields(_HeaderData)
])


@dataclasses.dataclass(frozen=True)
class HeaderData(_HeaderData):
    """An object containing headers data."""

    @classmethod
    def from_router_data(cls, router_data: dict) -> "HeaderData":
        """Create a HeaderData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A HeaderData object initialized with the provided router_data.
        """
        pass


@serializer(to=dict)
def _serialize_header_data(obj: HeaderData) -> dict:
    pass


@serializer(to=dict)
def serialize_frozen_dict_str_str(obj: _FrozenDictStrStr) -> dict:
    """Serialize a _FrozenDictStrStr object to a dict.

    Args:
        obj: the _FrozenDictStrStr object.

    Returns:
        A dict representation of the _FrozenDictStrStr object.
    """
    pass


class ReflexURL(str, _NetlocResultMixinStr):
    """A class representing a URL split result."""

    if TYPE_CHECKING:
        scheme: str
        netloc: str
        origin: str
        path: str
        query: str
        query_parameters: Mapping[str, str]
        fragment: str

    def __new__(cls, url: str):
        """Create a new ReflexURL instance.

        Args:
            url: the URL to split.

        Returns:
            A new ReflexURL instance.
        """
        (scheme, netloc, path, query, fragment) = urlsplit(url)
        obj = super().__new__(cls, url)
        object.__setattr__(obj, "scheme", scheme)
        object.__setattr__(obj, "netloc", netloc)
        object.__setattr__(obj, "path", path)
        object.__setattr__(obj, "query", query)
        object.__setattr__(obj, "origin", f"{scheme}://{netloc}")
        object.__setattr__(
            obj, "query_parameters", _FrozenDictStrStr(**dict(parse_qsl(query)))
        )
        object.__setattr__(obj, "fragment", fragment)
        return obj


@dataclasses.dataclass(frozen=True)
class PageData:
    """An object containing page data."""

    host: str = ""  # repeated with self.headers.origin (remove or keep the duplicate?)
    path: str = ""
    raw_path: str = ""
    full_path: str = ""
    full_raw_path: str = ""
    params: dict = dataclasses.field(default_factory=dict)

    @classmethod
    def from_router_data(cls, router_data: dict) -> "PageData":
        """Create a PageData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A PageData object initialized with the provided router_data.
        """
        pass


@serializer(to=dict)
def _serialize_page_data(obj: PageData) -> dict:
    pass


@dataclasses.dataclass(frozen=True)
class SessionData:
    """An object containing session data."""

    client_token: str = ""
    client_ip: str = ""
    session_id: str = ""

    @classmethod
    def from_router_data(cls, router_data: dict) -> "SessionData":
        """Create a SessionData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A SessionData object initialized with the provided router_data.
        """
        pass


@serializer(to=dict)
def _serialize_session_data(obj: SessionData) -> dict:
    pass


@dataclasses.dataclass(frozen=True)
class RouterData:
    """An object containing RouterData."""

    session: SessionData = dataclasses.field(default_factory=SessionData)
    headers: HeaderData = dataclasses.field(default_factory=HeaderData)
    _page: PageData = dataclasses.field(default_factory=PageData)
    url: ReflexURL = dataclasses.field(default=ReflexURL(""))
    route_id: str = ""

    @property
    def page(self) -> PageData:
        """Get the page data.

        Returns:
            The PageData object.
        """
        console.deprecate(
            feature_name="RouterData.page",
            reason="Use RouterData.url instead",
            deprecation_version="0.8.1",
            removal_version="1.0",
        )
        return self._page

    @classmethod
    def from_router_data(cls, router_data: dict) -> "RouterData":
        """Create a RouterData object from the given router_data.

        Args:
            router_data: the router_data dict.

        Returns:
            A RouterData object initialized with the provided router_data.
        """
        pass


@serializer(to=dict)
def serialize_router_data(obj: RouterData) -> dict:
    """Serialize a RouterData object to a dict.

    Args:
        obj: the RouterData object.

    Returns:
        A dict representation of the RouterData object.
    """
    pass
