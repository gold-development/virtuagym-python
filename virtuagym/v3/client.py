"""Synchronous client for the Virtuagym v3 API (OAuth client credentials).

Access tokens are requested and renewed automatically. Which resources are
available depends on the scopes Virtuagym registered for the OAuth client:
the schedule endpoints require the schedule integration scope
(schedule_public_api_club_<club_id>) and answer 401 "Token not valid."
without it, even with valid credentials.
"""

import time
from collections.abc import Iterator
from typing import Any

import httpx

from virtuagym.exceptions import VirtuaGymV3ApiError
from virtuagym.v3 import _core
from virtuagym.v3.models import BookingCreated, Lead, ScheduleEvent


class VirtuaGymClientV3:
    """Client for the Virtuagym v3 API."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        club_id: int,
        http: httpx.Client | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._club_id = club_id
        self._http = http or httpx.Client(timeout=30)
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    # ── Leads ──────────────────────────────────────────────────────────

    def leads(self, *, limit: int = 100) -> Iterator[list[Lead]]:
        """Yields leads page by page.

        The page/limit parameters are undocumented but verified live; the
        API defaults to 25 leads per page and ignores
        page_size/offset/sync_from.
        """
        page = 1
        while True:
            envelope = self._request(
                "GET", f"v3/clubs/{self._club_id}/leads", params={"page": page, "limit": limit}
            )
            rows = envelope.get("data", {}).get("leads", []) if isinstance(envelope, dict) else []
            leads = [Lead.model_validate(row) for row in rows]
            if leads:
                yield leads
            # The API reports no total; a short page means the end.
            if len(leads) < limit:
                return
            page += 1

    def all_leads(self, *, limit: int = 100) -> list[Lead]:
        """Retrieves every lead of the club across all pages."""
        return [lead for page in self.leads(limit=limit) for lead in page]

    def lead(self, lead_id: int | str) -> Lead:
        """Retrieves a single lead by its id (undocumented endpoint,
        verified live)."""
        envelope = self._request("GET", f"v3/clubs/{self._club_id}/leads/{lead_id}")
        row = envelope.get("data", {}).get("lead") if isinstance(envelope, dict) else None
        if row is None:
            raise VirtuaGymV3ApiError(404, f"Lead {lead_id} was not found in the response")
        return Lead.model_validate(row)

    def create_lead(self, data: dict[str, Any]) -> Lead:
        """Creates a lead and returns the canonical record (re-fetched). At
        least one of email/phone/mobile is required by the API."""
        return self._mutate_lead("POST", f"v3/clubs/{self._club_id}/leads", data)

    def update_lead(self, lead_id: int | str, data: dict[str, Any]) -> Lead:
        """Updates a lead and returns the canonical record."""
        return self._mutate_lead("PUT", f"v3/clubs/{self._club_id}/leads/{lead_id}", data)

    # ── Schedule (appointments) ────────────────────────────────────────

    def events(
        self,
        *,
        date_start: int,
        date_end: int,
        page_size: int = 100,
        deleted: bool | None = None,
        event_type: str | None = None,
    ) -> Iterator[list[ScheduleEvent]]:
        """Yields schedule events page by page (date range in UTC ms;
        event_type: 'appointment', 'group_class', 'staff_only', 'other')."""
        yield from self._event_pages(
            f"private/v3/clubs/{self._club_id}/schedule/integration/events",
            {
                "date_start": date_start,
                "date_end": date_end,
                "page_size": page_size,
                **({"deleted": _bool_str(deleted)} if deleted is not None else {}),
                **({"event_type": event_type} if event_type is not None else {}),
            },
        )

    def all_events(self, **kwargs: Any) -> list[ScheduleEvent]:
        return [event for page in self.events(**kwargs) for event in page]

    def event(self, event_id: str) -> ScheduleEvent:
        """Retrieves a single schedule event.

        Note: occurrences of a recurring event share the event_id (verified
        live); this endpoint takes no date parameter, so for recurring
        events it returns one occurrence of the API's choosing.
        """
        envelope = self._request(
            "GET", f"private/v3/clubs/{self._club_id}/schedule/integration/events/{event_id}"
        )
        row = envelope.get("data") if isinstance(envelope, dict) else None
        if row is None:
            raise VirtuaGymV3ApiError(404, f"Event {event_id} was not found in the response")
        return ScheduleEvent.model_validate(row)

    def event_bookings(
        self,
        *,
        date_start: int,
        date_end: int,
        page_size: int = 100,
        member_id: int | None = None,
        original_member_id: int | None = None,
        external_id: str | None = None,
        email: str | None = None,
        deleted: bool | None = None,
    ) -> Iterator[list[ScheduleEvent]]:
        """Yields events with their bookings page by page. The participant
        filters are mutually exclusive; a 204 ends the iteration."""
        params: dict[str, Any] = {
            "date_start": date_start,
            "date_end": date_end,
            "page_size": page_size,
        }
        for key, value in (
            ("member_id", member_id),
            ("original_member_id", original_member_id),
            ("external_id", external_id),
            ("email", email),
        ):
            if value is not None:
                params[key] = value
        if deleted is not None:
            params["deleted"] = _bool_str(deleted)
        yield from self._event_pages(
            f"private/v3/clubs/{self._club_id}/schedule/integration/events/bookings", params
        )

    def all_event_bookings(self, **kwargs: Any) -> list[ScheduleEvent]:
        return [event for page in self.event_bookings(**kwargs) for event in page]

    def create_booking(self, event_id: str, data: dict[str, Any]) -> BookingCreated:
        """Books a member (member_id/original_member_id) or a guest into an
        event; inspect the returned attempts' reason codes.

        NOTE (verified live): a member without the activity's credit type is
        still booked — as unpaid — rather than rejected with reason 105;
        check payment_info if payment matters.
        """
        envelope = self._request(
            "POST",
            f"private/v3/clubs/{self._club_id}/schedule/integration/events/{event_id}/bookings",
            json=data,
        )
        return BookingCreated.model_validate(envelope if isinstance(envelope, dict) else {})

    def update_booking(self, event_id: str, data: dict[str, Any]) -> None:
        """Updates an existing booking (e.g. presence) for a member or guest."""
        self._request(
            "PUT",
            f"private/v3/clubs/{self._club_id}/schedule/integration/events/{event_id}/bookings",
            json=data,
        )

    def cancel_booking(
        self,
        event_id: str,
        *,
        member_id: int | None = None,
        original_member_id: int | None = None,
        external_id: str | None = None,
        guest_email: str | None = None,
        refund: bool | None = None,
        free_cancellation_range: bool | None = None,
        cancellation_range: bool | None = None,
    ) -> None:
        """Cancels a booking (soft-delete; the event's spots_left is
        restored). Exactly one identifier must be given. The rule flags
        default to true on the API side."""
        params: dict[str, Any] = {}
        for key, value in (
            ("member_id", member_id),
            ("original_member_id", original_member_id),
            ("external_id", external_id),
            ("guest_email", guest_email),
        ):
            if value is not None:
                params[key] = value
        for key, flag in (
            ("refund", refund),
            ("free_cancellation_range", free_cancellation_range),
            ("cancellation_range", cancellation_range),
        ):
            if flag is not None:
                params[key] = _bool_str(flag)
        self._request(
            "DELETE",
            f"private/v3/clubs/{self._club_id}/schedule/integration/events/{event_id}/bookings",
            params=params,
        )

    # ── Internals ──────────────────────────────────────────────────────

    def _event_pages(self, path: str, params: dict[str, Any]) -> Iterator[list[ScheduleEvent]]:
        page = 1
        while True:
            envelope = self._request("GET", path, params={**params, "page": page})
            rows, total_pages = _core.events_page(envelope)
            events = [ScheduleEvent.model_validate(row) for row in rows]
            if events:
                yield events
            if not events or page >= (total_pages or page):
                return
            page += 1

    def _mutate_lead(self, method: str, path: str, data: dict[str, Any]) -> Lead:
        envelope = self._request(method, path, json=data)
        # The mutation response only carries the id (a string on create, a
        # number on update); re-fetch the canonical record.
        lead_id = envelope.get("data", {}).get("id") if isinstance(envelope, dict) else None
        if not isinstance(lead_id, (str, int)):
            raise VirtuaGymV3ApiError(0, "The lead mutation response did not contain an id")
        return self.lead(lead_id)

    def _token(self) -> str:
        if self._access_token is not None and time.time() < self._token_expires_at:
            return self._access_token
        response = self._http.post(
            _core.TOKEN_URL,
            headers={"x-represent-club-id": str(self._club_id)},
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
        )
        if response.is_error:
            raise _core.error_from_response(response) or _raise_for_status(response)
        token, expires_in = _core.parse_token_response(response.json())
        self._access_token = token
        self._token_expires_at = time.time() + max(expires_in - _core.TOKEN_EXPIRY_MARGIN, 0)
        return token

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any = None,
        _retry: bool = True,
    ) -> Any:
        token = self._token()
        response = self._http.request(
            method,
            f"{_core.GATEWAY_URL}/{path}",
            params=params,
            json=json,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401 and _retry:
            # The token may have been revoked; refresh and retry once.
            self._access_token = None
            return self._request(method, path, params, json, _retry=False)
        if response.is_error:
            raise _core.error_from_response(response) or _raise_for_status(response)
        return _core.body_or_none(response)


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _raise_for_status(response: httpx.Response) -> Exception:
    response.raise_for_status()
    return AssertionError("unreachable")  # pragma: no cover
