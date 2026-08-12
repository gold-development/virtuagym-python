"""Sans-IO helpers shared by the sync and async v3 clients."""

from typing import Any

import httpx

from virtuagym.exceptions import VirtuaGymV3ApiError

TOKEN_URL = "https://iam.services.virtuagym.com/auth/realms/virtuagym/protocol/openid-connect/token"
GATEWAY_URL = "https://gateway.services.virtuagym.com"

#: Renew the token a minute early so in-flight requests don't race expiry.
TOKEN_EXPIRY_MARGIN = 60


def error_from_response(response: httpx.Response) -> VirtuaGymV3ApiError | None:
    """Extracts the message from the three error shapes the v3 stack uses:
    leads ({status: "fail", error: {message}}), schedule ({message, fields?,
    status}) and the Keycloak token endpoint ({error, error_description?})."""
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    status = response.status_code

    error = data.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return VirtuaGymV3ApiError(status, error["message"])

    if isinstance(data.get("message"), str):
        fields = data.get("fields")
        return VirtuaGymV3ApiError(
            status, data["message"], list(fields) if isinstance(fields, list) else None
        )

    if isinstance(error, str):
        return VirtuaGymV3ApiError(status, data.get("error_description") or error)

    return None


def parse_token_response(data: Any) -> tuple[str, int]:
    if (
        isinstance(data, dict)
        and isinstance(data.get("access_token"), str)
        and isinstance(data.get("expires_in"), int)
    ):
        return data["access_token"], data["expires_in"]
    raise VirtuaGymV3ApiError(0, "The token response did not contain access_token/expires_in")


def body_or_none(response: httpx.Response) -> Any:
    """Returns the decoded body, or None for empty bodies (HTTP 204)."""
    if response.status_code == 204 or not response.content or not response.content.strip():
        return None
    return response.json()


def events_page(envelope: Any) -> tuple[list[Any], int | None]:
    data = envelope.get("data") if isinstance(envelope, dict) else None
    if not isinstance(data, dict):
        return [], None
    rows = data.get("events")
    total_pages = data.get("total_pages")
    return (
        rows if isinstance(rows, list) else [],
        total_pages if isinstance(total_pages, int) else None,
    )
