"""Sans-IO helpers shared by the sync and async v1 clients.

The v1 API reports errors in-band with HTTP 200 in two shapes (flat
``{statuscode, …}`` or nested ``{status: {…}, errors?}``); some endpoints
(e.g. bodymetrics) use real HTTP status codes and a FLAT success envelope
instead. Pagination cursors differ per endpoint — every rule below was
verified against the live API (see API-FINDINGS.md in
gold-development/virtuagym-node).
"""

from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import httpx

from virtuagym.exceptions import VirtuaGymApiError

BASE_URL = "https://api.virtuagym.com/api/v1"

Status = dict[str, Any]
Params = dict[str, Any]
#: (status, last_item_raw, params) -> params for the next page, or None to stop.
Advance = Callable[[Status, Any, Params], Params | None]


def parse_envelope(response: httpx.Response) -> tuple[Status, Any]:
    """Normalizes the three envelope shapes and raises on API errors."""
    try:
        data = response.json()
    except ValueError as error:  # pragma: no cover - defensive
        raise VirtuaGymApiError(0, "The response body was not valid JSON") from error
    if not isinstance(data, dict):
        raise VirtuaGymApiError(0, "The response body was not a JSON object")

    # Flat error envelope: {statuscode, statusmessage, ...} — used both
    # in-band with HTTP 200 and with real HTTP error codes.
    if "statuscode" in data and not _is_success(int(data["statuscode"])):
        raise VirtuaGymApiError(
            int(data["statuscode"]), str(data.get("statusmessage", "")), data.get("errors")
        )

    status = data.get("status")
    if isinstance(status, dict) and "statuscode" in status:
        if not _is_success(int(status["statuscode"])):
            raise VirtuaGymApiError(
                int(status["statuscode"]), str(status.get("statusmessage", "")), data.get("errors")
            )
        return status, data.get("result")

    # Flat success envelope (e.g. bodymetrics): status fields at top level.
    if "statuscode" in data:
        return data, data.get("result")

    raise VirtuaGymApiError(0, "The response had no status envelope")


def _is_success(statuscode: int) -> bool:
    return 200 <= statuscode < 300


def parse_next_page(next_page: Any) -> Params:
    """Parses the undocumented server-computed next_page cursor
    ("sync_from=1784035004986", optionally with from_id)."""
    if not isinstance(next_page, str) or next_page == "":
        return {}
    values = parse_qs(next_page)
    parsed: Params = {}
    for key in ("sync_from", "from_id"):
        raw = values.get(key, [None])[0]
        if raw is not None and raw.lstrip("-").isdigit():
            parsed[key] = int(raw)
    return parsed


def wrap_list(result: Any) -> list[Any]:
    """Single-resource GETs return one-element arrays, but the docs show
    bare objects; accept both."""
    if isinstance(result, dict):
        return [result]
    return result if isinstance(result, list) else []


def remaining(status: Status) -> int:
    value = status.get("results_remaining")
    return int(value) if isinstance(value, (int, float)) else 0


def advance_member_cursor(status: Status, last: Any, params: Params) -> Params | None:
    """Employees/members: prefer next_page; fall back to the last row's
    timestamp_edit + member_id."""
    if remaining(status) <= 0 or last is None:
        return None
    nxt = dict(params)
    cursor = parse_next_page(status.get("next_page"))
    if cursor:
        nxt["sync_from"] = cursor.get("sync_from", nxt.get("sync_from", 0))
        nxt.pop("from_id", None)
        if "from_id" in cursor:
            nxt["from_id"] = cursor["from_id"]
    else:
        nxt["sync_from"] = last["timestamp_edit"]
        nxt["from_id"] = last["member_id"]
    return nxt


def advance_instance_cursor(status: Status, last: Any, params: Params) -> Params | None:
    """Membership instances: results are ordered by instance_id and from_id
    is INCLUSIVE, while the next_page sync_from cursor duplicates rows on
    timestamp ties — so page on instance_id + 1."""
    if remaining(status) <= 0 or last is None:
        return None
    return {**params, "from_id": last["instance_id"] + 1}


def advance_page_param(status: Status, last: Any, params: Params) -> Params | None:
    """Membership definitions / invoices: the page parameter paginates
    exactly (25/page resp. 500/page)."""
    if remaining(status) <= 0 or last is None:
        return None
    return {**params, "page": params.get("page", 1) + 1}


def make_sync_from_advancer(fallback_field: str, *, require_progress: bool = False) -> Advance:
    """Events/participants/visits/credits: no documented cursor; prefer the
    server-computed next_page and guard against a non-advancing fallback."""

    def advance(status: Status, last: Any, params: Params) -> Params | None:
        if remaining(status) <= 0 or last is None:
            return None
        sync_from = params.get("sync_from", 0)
        cursor = parse_next_page(status.get("next_page"))
        if "sync_from" in cursor and (not require_progress or cursor["sync_from"] != sync_from):
            return {**params, "sync_from": cursor["sync_from"]}
        fallback = last.get(fallback_field) if isinstance(last, dict) else None
        if isinstance(fallback, int) and fallback > sync_from:
            return {**params, "sync_from": fallback}
        # status.timestamp keeps the events endpoint moving when no
        # per-item cursor exists.
        timestamp = status.get("timestamp")
        if fallback_field == "" and isinstance(timestamp, int) and timestamp > sync_from:
            return {**params, "sync_from": timestamp}
        return None

    return advance


#: Club events advance on next_page or the response's status.timestamp.
advance_event_cursor = make_sync_from_advancer("")
advance_participant_cursor = make_sync_from_advancer("timestamp_edit")
advance_visit_cursor = make_sync_from_advancer("check_in_timestamp")
advance_credit_cursor = make_sync_from_advancer("timestamp_edited", require_progress=True)


def drop_query_none(params: Params) -> Params:
    return {key: value for key, value in params.items() if value is not None}


def error_from_http_status(response: httpx.Response) -> VirtuaGymApiError | None:
    """Maps real-HTTP-status errors (bodymetrics style) to the same
    exception as in-band errors."""
    try:
        data = response.json()
    except ValueError:
        return None
    if isinstance(data, dict) and "statuscode" in data and "statusmessage" in data:
        return VirtuaGymApiError(
            int(data["statuscode"]), str(data["statusmessage"]), data.get("errors")
        )
    return None
