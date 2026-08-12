"""Exceptions raised by the Virtuagym clients."""

from typing import Any


class VirtuaGymApiError(Exception):
    """An error reported by the Virtuagym v1 API itself.

    Note these can arrive with HTTP 200 — the v1 API reports errors
    in-band. Schema-validation failures also surface as this error.
    """

    def __init__(self, statuscode: int, statusmessage: str, errors: Any = None) -> None:
        super().__init__(f"Virtuagym API error {statuscode}: {statusmessage}")
        self.statuscode = statuscode
        self.statusmessage = statusmessage
        #: Validation error details, when the endpoint provides them.
        self.errors = errors


class VirtuaGymV3ApiError(Exception):
    """An error reported by the Virtuagym v3 API.

    Unlike v1, the v3 endpoints use real HTTP status codes for errors.
    """

    def __init__(self, http_status: int, message: str, fields: list[str] | None = None) -> None:
        super().__init__(f"Virtuagym API v3 error {http_status}: {message}")
        self.http_status = http_status
        #: Invalid fields, when the endpoint reports them.
        self.fields = fields
