"""Typed Python client for the Virtuagym API (v1 + v3), sync + async."""

from virtuagym.exceptions import VirtuaGymApiError, VirtuaGymV3ApiError
from virtuagym.v1.async_client import AsyncVirtuaGymClientV1
from virtuagym.v1.client import VirtuaGymClientV1
from virtuagym.v3.async_client import AsyncVirtuaGymClientV3
from virtuagym.v3.client import VirtuaGymClientV3

__all__ = [
    "AsyncVirtuaGymClientV1",
    "AsyncVirtuaGymClientV3",
    "VirtuaGymApiError",
    "VirtuaGymClientV1",
    "VirtuaGymClientV3",
    "VirtuaGymV3ApiError",
]
