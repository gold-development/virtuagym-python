"""Synchronous client for the Virtuagym v1 API (api key + club secret)."""

from collections.abc import Iterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from virtuagym.exceptions import VirtuaGymApiError
from virtuagym.v1 import _core
from virtuagym.v1.models import (
    ActivateUserResult,
    Bodymetric,
    BodymetricUpdated,
    ClubEvent,
    ClubTax,
    CreditTransaction,
    Employee,
    EventParticipant,
    EventParticipantCreated,
    IncomeCategory,
    Invoice,
    Member,
    MemberCredit,
    MemberNote,
    MemberNoteCreated,
    MembershipContract,
    MembershipDefinition,
    MembershipInstance,
    Visit,
    VisitRegistered,
)

_M = TypeVar("_M", bound=BaseModel)


class VirtuaGymClientV1:
    """Client for the Virtuagym v1 API.

    Pagination quirks per endpoint were verified against the live API —
    see API-FINDINGS.md in gold-development/virtuagym-node.
    """

    def __init__(
        self,
        api_key: str,
        club_secret: str,
        club_id: int,
        http: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._club_secret = club_secret
        self._club_id = club_id
        self._http = http or httpx.Client(timeout=30)

    # ── Employees ──────────────────────────────────────────────────────

    def employees(
        self,
        *,
        sync_from: int = 0,
        club_member_id: int | None = None,
        rfid_tag: str | None = None,
        any_sub_club: bool = False,
        with_: str | None = None,
    ) -> Iterator[list[Employee]]:
        """Yields employees page by page, fetching each page lazily.

        ``sync_from`` is a millisecond timestamp for incremental sync.
        """
        params = _core.drop_query_none(
            {
                "sync_from": sync_from,
                "club_member_id": club_member_id,
                "rfid_tag": rfid_tag,
                "any_sub_club": "1" if any_sub_club else None,
                "with": with_,
            }
        )
        yield from self._pages(
            Employee, f"club/{self._club_id}/employee", params, _core.advance_member_cursor
        )

    def all_employees(self, **kwargs: Any) -> list[Employee]:
        """Retrieves every employee across all pages."""
        return _core.latest_by_key(
            [employee for page in self.employees(**kwargs) for employee in page],
            lambda employee: employee.member_id,
        )

    def employee(
        self, member_id: int, *, any_sub_club: bool = False, with_: str | None = None
    ) -> Employee:
        """Retrieves a single employee by member ID.

        Raises :class:`VirtuaGymApiError` (statuscode 420) when the employee
        does not exist or does not belong to the club.
        """
        params = _core.drop_query_none(
            {"any_sub_club": "1" if any_sub_club else None, "with": with_}
        )
        return self._single(
            Employee,
            f"club/{self._club_id}/employee/{member_id}",
            params,
            f"Employee {member_id} was not found in the response",
        )

    def create_employee(self, data: dict[str, Any]) -> Employee:
        """Creates a new employee (wire-format fields: firstname, lastname, …)."""
        return self._mutate_employee(f"club/{self._club_id}/employee", data)

    def update_employee(self, member_id: int, data: dict[str, Any]) -> Employee:
        """Updates an existing employee."""
        return self._mutate_employee(f"club/{self._club_id}/employee/{member_id}", data)

    def create_or_update_employee(self, data: dict[str, Any]) -> Employee:
        """Creates or updates the employee matched on external_id (mandatory)."""
        return self._mutate_employee(f"club/{self._club_id}/employee/create_or_update", data)

    # ── Members ────────────────────────────────────────────────────────

    def members(
        self,
        *,
        sync_from: int = 0,
        club_member_id: int | None = None,
        rfid_tag: str | None = None,
        external_id: str | None = None,
        email: str | None = None,
        any_sub_club: bool = False,
        with_: str | None = None,
    ) -> Iterator[list[Member]]:
        """Yields members page by page, fetching each page lazily."""
        params = _core.drop_query_none(
            {
                "sync_from": sync_from,
                "club_member_id": club_member_id,
                "rfid_tag": rfid_tag,
                "external_id": external_id,
                "email": email,
                "any_sub_club": "1" if any_sub_club else None,
                "with": with_,
            }
        )
        yield from self._pages(
            Member, f"club/{self._club_id}/member", params, _core.advance_member_cursor
        )

    def all_members(self, **kwargs: Any) -> list[Member]:
        """Retrieves every member across all pages."""
        return _core.latest_by_key(
            [member for page in self.members(**kwargs) for member in page],
            lambda member: member.member_id,
        )

    def member(
        self, member_id: int, *, any_sub_club: bool = False, with_: str | None = None
    ) -> Member:
        """Retrieves a single member; ``with_`` accepts 'memberships' or
        'active_memberships'."""
        params = _core.drop_query_none(
            {"any_sub_club": "1" if any_sub_club else None, "with": with_}
        )
        return self._single(
            Member,
            f"club/{self._club_id}/member/{member_id}",
            params,
            f"Member {member_id} was not found in the response",
        )

    def create_member(self, data: dict[str, Any]) -> Member:
        """Creates a new member (wire-format fields: firstname, lastname, …)."""
        return self._mutate_member(f"club/{self._club_id}/member", data)

    def update_member(self, member_id: int, data: dict[str, Any]) -> Member:
        """Updates an existing member."""
        return self._mutate_member(f"club/{self._club_id}/member/{member_id}", data)

    def create_or_update_member(self, data: dict[str, Any]) -> Member:
        """Creates or updates the member matched on external_id (mandatory);
        also transfers between sub-clubs via club_external_id."""
        return self._mutate_member(f"club/{self._club_id}/member/create_or_update", data)

    def activate_user(self, data: dict[str, Any]) -> ActivateUserResult:
        """Activates a user profile for a member, or connects to an existing
        one (connect_to_existing)."""
        _, result = self._request("POST", f"club/{self._club_id}/member/activate_user", json=data)
        return ActivateUserResult.model_validate(result)

    # ── Club events ────────────────────────────────────────────────────

    def events(
        self,
        *,
        sync_from: int = 0,
        timestamp_start: int | None = None,
        timestamp_end: int | None = None,
        member_id: int | None = None,
        schedule_id: int | None = None,
    ) -> Iterator[list[ClubEvent]]:
        """Yields club events page by page (timestamps in seconds)."""
        params = _core.drop_query_none(
            {
                "sync_from": sync_from,
                "timestamp_start": timestamp_start,
                "timestamp_end": timestamp_end,
                "member_id": member_id,
                "schedule_id": schedule_id,
            }
        )
        yield from self._pages(
            ClubEvent, f"club/{self._club_id}/events", params, _core.advance_event_cursor
        )

    def all_events(self, **kwargs: Any) -> list[ClubEvent]:
        """Retrieves every club event matching the query across all pages."""
        return [event for page in self.events(**kwargs) for event in page]

    def event(self, event_id: str, *, sync_from: int = 0) -> ClubEvent:
        """Retrieves a single club event by event ID."""
        return self._single(
            ClubEvent,
            f"club/{self._club_id}/events/{event_id}",
            {"sync_from": sync_from},
            f"Event {event_id} was not found in the response",
        )

    # ── Memberships ────────────────────────────────────────────────────

    def membership_instances(
        self, *, sync_from: int = 0, member_id: int | None = None
    ) -> Iterator[list[MembershipInstance]]:
        """Yields membership instances page by page.

        from_id is sent from the very first call: without it the API orders
        results by timestamp instead of instance_id and the cursor tears.
        """
        params = _core.drop_query_none(
            {"sync_from": sync_from, "from_id": 0, "member_id": member_id}
        )
        yield from self._pages(
            MembershipInstance,
            f"club/{self._club_id}/membership/instance",
            params,
            _core.advance_instance_cursor,
        )

    def all_membership_instances(self, **kwargs: Any) -> list[MembershipInstance]:
        return [instance for page in self.membership_instances(**kwargs) for instance in page]

    def create_membership_instance(self, data: dict[str, Any]) -> MembershipContract:
        """Creates a membership instance (contract) for a member."""
        _, result = self._request("POST", f"club/{self._club_id}/membership/instance", json=data)
        return MembershipContract.model_validate(result)

    def membership_definitions(
        self, *, sync_from: int = 0, status: str | None = None
    ) -> Iterator[list[MembershipDefinition]]:
        """Yields membership definitions page by page (25 per page);
        ``status`` accepts 'all' (API default), 'active' or 'inactive'."""
        params = _core.drop_query_none({"sync_from": sync_from, "status": status})
        yield from self._pages(
            MembershipDefinition,
            f"club/{self._club_id}/membership/definition",
            params,
            _core.advance_page_param,
        )

    def all_membership_definitions(self, **kwargs: Any) -> list[MembershipDefinition]:
        return [d for page in self.membership_definitions(**kwargs) for d in page]

    # ── Event participants (bookings) ──────────────────────────────────

    def event_participants(
        self,
        *,
        sync_from: int = 0,
        timestamp_start: int | None = None,
        timestamp_end: int | None = None,
        event_id: str | None = None,
        fill_guestname: bool = False,
    ) -> Iterator[list[EventParticipant]]:
        """Yields event participants page by page. Without event_id the API
        defaults the window to (today - 1 month) .. (today + 1 month)."""
        params = _core.drop_query_none(
            {
                "sync_from": sync_from,
                "timestamp_start": timestamp_start,
                "timestamp_end": timestamp_end,
                "event_id": event_id,
                "fill_guestname": "1" if fill_guestname else None,
            }
        )
        yield from self._pages(
            EventParticipant,
            f"club/{self._club_id}/eventparticipants",
            params,
            _core.advance_participant_cursor,
        )

    def all_event_participants(self, **kwargs: Any) -> list[EventParticipant]:
        return [p for page in self.event_participants(**kwargs) for p in page]

    def event_participant(
        self, event_participant_id: int, *, sync_from: int = 0, fill_guestname: bool = False
    ) -> EventParticipant:
        """Retrieves a single event participant (booking) by its ID."""
        params = _core.drop_query_none(
            {"sync_from": sync_from, "fill_guestname": "1" if fill_guestname else None}
        )
        return self._single(
            EventParticipant,
            f"club/{self._club_id}/eventparticipants/{event_participant_id}",
            params,
            f"Event participant {event_participant_id} was not found in the response",
        )

    def create_event_participant(self, data: dict[str, Any]) -> EventParticipantCreated:
        """Books a member into an event. Store event_participant_id; it is
        needed to update or cancel the booking."""
        _, result = self._request("POST", f"club/{self._club_id}/eventparticipants", json=data)
        return EventParticipantCreated.model_validate(result)

    def update_event_participant(self, event_participant_id: int, *, ticket_printed: bool) -> None:
        """Updates a booking; the API currently only supports ticket_printed."""
        self._request(
            "PUT",
            f"club/{self._club_id}/eventparticipants",
            json={"event_participant_id": event_participant_id, "ticket_printed": ticket_printed},
        )

    def delete_event_participant(self, event_participant_id: int) -> None:
        """Cancels the booking."""
        self._request("DELETE", f"club/{self._club_id}/eventparticipants/{event_participant_id}")

    # ── Club taxes & income categories ─────────────────────────────────

    def club_taxes(self) -> list[ClubTax]:
        """Retrieves all club taxes (not paginated). The undocumented
        club_tax_id is the numeric id referenced by invoice rows and
        membership-instance creation."""
        _, result = self._request("GET", f"club/{self._club_id}/club-taxes")
        return [ClubTax.model_validate(item) for item in result or []]

    def income_categories(self) -> list[IncomeCategory]:
        """Retrieves all income categories (not paginated)."""
        _, result = self._request("GET", f"club/{self._club_id}/income-categories")
        return [IncomeCategory.model_validate(item) for item in result or []]

    # ── Invoices ───────────────────────────────────────────────────────

    def invoices(self) -> Iterator[list[Invoice]]:
        """Yields invoices page by page (500/page); the endpoint supports no
        filters (sync_from is silently ignored)."""
        yield from self._pages(
            Invoice, f"club/{self._club_id}/invoices", {}, _core.advance_page_param
        )

    def all_invoices(self) -> list[Invoice]:
        return [invoice for page in self.invoices() for invoice in page]

    def invoice(self, guid: str) -> Invoice:
        """Retrieves a single invoice by its guid (the live API only
        resolves invoices by guid, not by numeric id)."""
        return self._single(
            Invoice,
            f"club/{self._club_id}/invoices/{guid}",
            {},
            f"Invoice {guid} was not found in the response",
        )

    def create_invoice(self, data: dict[str, Any]) -> Invoice:
        """Creates an invoice for a member (wire-format fields: member_id,
        payment_method?, rows)."""
        _, result = self._request("POST", f"club/{self._club_id}/invoices", json=data)
        return Invoice.model_validate(result)

    # ── Visits ─────────────────────────────────────────────────────────

    def visits(self, *, sync_from: int = 0, member_id: int | None = None) -> Iterator[list[Visit]]:
        """Yields visits page by page."""
        params = _core.drop_query_none({"sync_from": sync_from, "member_id": member_id})
        yield from self._pages(
            Visit, f"club/{self._club_id}/visits", params, _core.advance_visit_cursor
        )

    def all_visits(self, **kwargs: Any) -> list[Visit]:
        return [visit for page in self.visits(**kwargs) for visit in page]

    def visit(self, visit_id: int) -> Visit:
        """Retrieves a single visit by its id."""
        return self._single(
            Visit,
            f"club/{self._club_id}/visits/{visit_id}",
            {},
            f"Visit {visit_id} was not found in the response",
        )

    def create_visit(self, data: dict[str, Any]) -> VisitRegistered:
        """Registers a check-in/check-out (member_id or rfid_tag, action?)."""
        _, result = self._request("POST", f"club/{self._club_id}/visits", json=data)
        return VisitRegistered.model_validate(result)

    # ── Member notes ───────────────────────────────────────────────────

    def member_notes(
        self, *, sync_from: int = 0, member_id: int | None = None, note_type: str | None = None
    ) -> list[MemberNote]:
        """Retrieves member notes.

        WARNING: the API caps this endpoint at the newest 500 notes and
        ignores every pagination parameter (verified live). ``sync_from``
        is in SECONDS here, unlike most endpoints.
        """
        params = _core.drop_query_none(
            {"sync_from": sync_from, "member_id": member_id, "note_type": note_type}
        )
        _, result = self._request("GET", f"club/{self._club_id}/notes", params=params)
        return [MemberNote.model_validate(item) for item in result or []]

    def member_note(self, note_id: int) -> MemberNote:
        """Retrieves a single note by its id."""
        return self._single(
            MemberNote,
            f"club/{self._club_id}/notes/{note_id}",
            {"sync_from": 0},
            f"Note {note_id} was not found in the response",
        )

    def create_member_note(self, data: dict[str, Any]) -> MemberNoteCreated:
        """Creates a note (wire-format fields: member_id, member_from,
        note_type, note_text)."""
        _, result = self._request("POST", f"club/{self._club_id}/notes", json=data)
        return MemberNoteCreated.model_validate(result)

    def update_member_note(
        self, note_id: int, *, note_text: str | None = None, note_type: str | None = None
    ) -> None:
        """Updates a note's text and/or type (at least one must be given)."""
        if note_text is None and note_type is None:
            raise ValueError("At least one of note_text / note_type must be given.")
        body = _core.drop_query_none(
            {"note_id": note_id, "note_text": note_text, "note_type": note_type}
        )
        self._request("PUT", f"club/{self._club_id}/notes", json=body)

    def delete_member_note(self, note_id: int) -> None:
        """Deletes the note."""
        self._request("DELETE", f"club/{self._club_id}/notes/{note_id}")

    # ── Member credits ─────────────────────────────────────────────────

    def member_credits(
        self, *, sync_from: int = 0, member_id: int | None = None
    ) -> Iterator[list[MemberCredit]]:
        """Yields credit rows page by page; without member_id the whole club
        is listed. ``sync_from`` is in SECONDS live (the docs claim ms).

        The seconds-resolution cursor is inclusive, so rows sharing the
        boundary timestamp repeat on the next page; repeats are dropped
        (identity is member_id + service_type).
        """
        params = _core.drop_query_none({"sync_from": sync_from, "member_id": member_id})
        seen: set[str] = set()
        for page in self._pages(
            MemberCredit, f"club/{self._club_id}/credit", params, _core.advance_credit_cursor
        ):
            fresh = []
            for credit in page:
                key = f"{credit.member_id}|{credit.service_type}"
                if key not in seen:
                    seen.add(key)
                    fresh.append(credit)
            if fresh:
                yield fresh

    def all_member_credits(self, **kwargs: Any) -> list[MemberCredit]:
        return [credit for page in self.member_credits(**kwargs) for credit in page]

    def add_member_credits(self, data: dict[str, Any]) -> CreditTransaction:
        """Assigns credits (one member, one service type per request). The
        client_id GUID in ``data`` makes retries idempotent."""
        _, result = self._request("PUT", f"club/{self._club_id}/credit", json=data)
        return CreditTransaction.model_validate(result)

    # ── Workouts & bodymetrics ─────────────────────────────────────────

    def assign_workout(self, data: dict[str, Any]) -> None:
        """Assigns a workout (wire-format fields: plan_id, user_id — the
        linked account id, not member_id — weeks, weekdays, start_date)."""
        # Uniquely, the success response carries no result field at all.
        self._request("POST", f"club/{self._club_id}/member/workouts", json=data)

    def bodymetrics(
        self, member_id: int, *, sync_from: int = 0, type: str | None = None
    ) -> list[Bodymetric]:
        """Retrieves the full bodymetric history of a member (not
        paginated). Requires an activated user profile."""
        params = _core.drop_query_none(
            {"sync_from": sync_from, "member_id": member_id, "type": type}
        )
        _, result = self._request("GET", f"club/{self._club_id}/bodymetrics", params=params)
        return [Bodymetric.model_validate(item) for item in result or []]

    def bodymetric(self, bodymetric_id: int, member_id: int) -> Bodymetric:
        """Retrieves a single bodymetric entry; the owning member's id is
        required by the API."""
        return self._single(
            Bodymetric,
            f"club/{self._club_id}/bodymetrics/{bodymetric_id}",
            {"member_id": member_id},
            f"Bodymetric {bodymetric_id} was not found in the response",
        )

    def update_bodymetric(self, data: dict[str, Any]) -> BodymetricUpdated:
        """Records a bodymetric value (wire-format fields: member_id, type,
        value)."""
        _, result = self._request("PUT", f"club/{self._club_id}/bodymetrics", json=data)
        return BodymetricUpdated.model_validate(result)

    # ── Internals ──────────────────────────────────────────────────────

    def _pages(
        self,
        model: type[_M],
        path: str,
        params: _core.Params,
        advance: _core.Advance,
    ) -> Iterator[list[_M]]:
        while True:
            status, result = self._request("GET", path, params=params)
            rows = result if isinstance(result, list) else []
            items = [model.model_validate(row) for row in rows]
            if items:
                yield items
            next_params = advance(status, rows[-1] if rows else None, params)
            if next_params is None:
                return
            params = next_params

    def _single(self, model: type[_M], path: str, params: _core.Params, not_found: str) -> _M:
        _, result = self._request("GET", path, params=params)
        rows = _core.wrap_list(result)
        if not rows:
            raise VirtuaGymApiError(420, not_found)
        return model.model_validate(rows[0])

    def _mutate_member(self, path: str, data: dict[str, Any]) -> Member:
        _, result = self._request("PUT", path, json=data)
        member_id = _extract_member_id(result)
        # PUT responses are inconsistent (booleans as 0/1, timestamps as
        # date strings, missing fields), so re-fetch the canonical record.
        try:
            return self.member(member_id)
        except VirtuaGymApiError:
            # After a sub-club transfer the member no longer belongs to this
            # club id; retry across the chain.
            return self.member(member_id, any_sub_club=True)

    def _mutate_employee(self, path: str, data: dict[str, Any]) -> Employee:
        _, result = self._request("PUT", path, json=data)
        return self.employee(_extract_member_id(result))

    def _request(
        self,
        method: str,
        path: str,
        params: _core.Params | None = None,
        json: Any = None,
    ) -> tuple[_core.Status, Any]:
        query = dict(params or {})
        query["api_key"] = self._api_key
        query["club_secret"] = self._club_secret
        response = self._http.request(method, f"{_core.BASE_URL}/{path}", params=query, json=json)
        if response.is_error:
            error = _core.error_from_http_status(response)
            if error is not None:
                raise error
            response.raise_for_status()
        return _core.parse_envelope(response)


def _extract_member_id(result: Any) -> int:
    if isinstance(result, dict) and str(result.get("member_id", "")).isdigit():
        return int(result["member_id"])
    raise VirtuaGymApiError(0, "The mutation response did not contain a member_id")
