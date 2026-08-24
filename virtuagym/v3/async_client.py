"""Asynchronous client for the Virtuagym v3 API.

Method-by-method mirror of :class:`virtuagym.v3.client.VirtuaGymClientV3`;
see that class for detailed per-endpoint documentation.
"""

import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from virtuagym.exceptions import VirtuaGymV3ApiError
from virtuagym.v3 import _core
from virtuagym.v3.client import _bool_str, _raise_for_status
from virtuagym.v3.models import BookingCreated, Lead, ScheduleEvent


class AsyncVirtuaGymClientV3:
    """Async client for the Virtuagym v3 API."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        club_id: int,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._club_id = club_id
        self._http = http or httpx.AsyncClient(timeout=30)
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    async def leads(self, *, limit: int = 100) -> AsyncIterator[list[Lead]]:
        page = 1
        while True:
            envelope = await self._request(
                "GET", f"v3/clubs/{self._club_id}/leads", params={"page": page, "limit": limit}
            )
            rows = envelope.get("data", {}).get("leads", []) if isinstance(envelope, dict) else []
            leads = [Lead.model_validate(row) for row in rows]
            if leads:
                yield leads
            if len(leads) < limit:
                return
            page += 1

    async def all_leads(self, *, limit: int = 100) -> list[Lead]:
        return [lead async for page in self.leads(limit=limit) for lead in page]

    async def lead(self, lead_id: int | str) -> Lead:
        envelope = await self._request("GET", f"v3/clubs/{self._club_id}/leads/{lead_id}")
        row = envelope.get("data", {}).get("lead") if isinstance(envelope, dict) else None
        if row is None:
            raise VirtuaGymV3ApiError(404, f"Lead {lead_id} was not found in the response")
        return Lead.model_validate(row)

    async def create_lead(self, data: dict[str, Any]) -> Lead:
        return await self._mutate_lead("POST", f"v3/clubs/{self._club_id}/leads", data)

    async def update_lead(self, lead_id: int | str, data: dict[str, Any]) -> Lead:
        return await self._mutate_lead("PUT", f"v3/clubs/{self._club_id}/leads/{lead_id}", data)

    async def events(
        self,
        *,
        date_start: int,
        date_end: int,
        page_size: int = 100,
        deleted: bool | None = None,
        event_type: str | None = None,
    ) -> AsyncIterator[list[ScheduleEvent]]:
        async for page in self._event_pages(
            f"private/v3/clubs/{self._club_id}/schedule/integration/events",
            {
                "date_start": date_start,
                "date_end": date_end,
                "page_size": page_size,
                **({"deleted": _bool_str(deleted)} if deleted is not None else {}),
                **({"event_type": event_type} if event_type is not None else {}),
            },
        ):
            yield page

    async def all_events(self, **kwargs: Any) -> list[ScheduleEvent]:
        return [event async for page in self.events(**kwargs) for event in page]

    async def event(self, event_id: str) -> ScheduleEvent:
        envelope = await self._request(
            "GET", f"private/v3/clubs/{self._club_id}/schedule/integration/events/{event_id}"
        )
        row = envelope.get("data") if isinstance(envelope, dict) else None
        if row is None:
            raise VirtuaGymV3ApiError(404, f"Event {event_id} was not found in the response")
        return ScheduleEvent.model_validate(row)

    async def event_bookings(
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
    ) -> AsyncIterator[list[ScheduleEvent]]:
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
        async for page in self._event_pages(
            f"private/v3/clubs/{self._club_id}/schedule/integration/events/bookings", params
        ):
            yield page

    async def all_event_bookings(self, **kwargs: Any) -> list[ScheduleEvent]:
        return [event async for page in self.event_bookings(**kwargs) for event in page]

    async def create_booking(self, event_id: str, data: dict[str, Any]) -> BookingCreated:
        envelope = await self._request(
            "POST",
            f"private/v3/clubs/{self._club_id}/schedule/integration/events/{event_id}/bookings",
            json=data,
        )
        return BookingCreated.model_validate(envelope if isinstance(envelope, dict) else {})

    async def update_booking(self, event_id: str, data: dict[str, Any]) -> None:
        await self._request(
            "PUT",
            f"private/v3/clubs/{self._club_id}/schedule/integration/events/{event_id}/bookings",
            json=data,
        )

    async def cancel_booking(
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
        await self._request(
            "DELETE",
            f"private/v3/clubs/{self._club_id}/schedule/integration/events/{event_id}/bookings",
            params=params,
        )

    # ── Internals ──────────────────────────────────────────────────────

    async def _event_pages(
        self, path: str, params: dict[str, Any]
    ) -> AsyncIterator[list[ScheduleEvent]]:
        # Pages can overlap at the boundary (unstable sort on
        # datetime_start ties); repeated occurrences are dropped.
        seen: set[str] = set()
        page = 1
        while True:
            envelope = await self._request("GET", path, params={**params, "page": page})
            rows, total_pages = _core.events_page(envelope)
            fresh = _core.dedupe_occurrences(rows, seen)
            events = [ScheduleEvent.model_validate(row) for row in fresh]
            if events:
                yield events
            if not rows or page >= (total_pages or page):
                return
            page += 1

    async def _mutate_lead(self, method: str, path: str, data: dict[str, Any]) -> Lead:
        envelope = await self._request(method, path, json=data)
        lead_id = envelope.get("data", {}).get("id") if isinstance(envelope, dict) else None
        if not isinstance(lead_id, (str, int)):
            raise VirtuaGymV3ApiError(0, "The lead mutation response did not contain an id")
        return await self.lead(lead_id)

    async def _token(self) -> str:
        if self._access_token is not None and time.time() < self._token_expires_at:
            return self._access_token
        response = await self._http.post(
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

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: Any = None,
        _retry: bool = True,
    ) -> Any:
        token = await self._token()
        response = await self._http.request(
            method,
            f"{_core.GATEWAY_URL}/{path}",
            params=params,
            json=json,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401 and _retry:
            self._access_token = None
            return await self._request(method, path, params, json, _retry=False)
        if response.is_error:
            raise _core.error_from_response(response) or _raise_for_status(response)
        return _core.body_or_none(response)
