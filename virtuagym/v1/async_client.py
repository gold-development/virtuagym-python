"""Asynchronous client for the Virtuagym v1 API.

Method-by-method mirror of :class:`virtuagym.v1.client.VirtuaGymClientV1`;
see that class for detailed per-endpoint documentation.
"""

from collections.abc import AsyncIterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from virtuagym.exceptions import VirtuaGymApiError
from virtuagym.v1 import _core
from virtuagym.v1.client import _extract_member_id
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


class AsyncVirtuaGymClientV1:
    """Async client for the Virtuagym v1 API."""

    def __init__(
        self,
        api_key: str,
        club_secret: str,
        club_id: int,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._club_secret = club_secret
        self._club_id = club_id
        self._http = http or httpx.AsyncClient(timeout=30)

    async def employees(
        self,
        *,
        sync_from: int = 0,
        club_member_id: int | None = None,
        rfid_tag: str | None = None,
        any_sub_club: bool = False,
        with_: str | None = None,
    ) -> AsyncIterator[list[Employee]]:
        params = _core.drop_query_none(
            {
                "sync_from": sync_from,
                "club_member_id": club_member_id,
                "rfid_tag": rfid_tag,
                "any_sub_club": "1" if any_sub_club else None,
                "with": with_,
            }
        )
        async for page in self._pages(
            Employee, f"club/{self._club_id}/employee", params, _core.advance_member_cursor
        ):
            yield page

    async def all_employees(self, **kwargs: Any) -> list[Employee]:
        return [employee async for page in self.employees(**kwargs) for employee in page]

    async def employee(
        self, member_id: int, *, any_sub_club: bool = False, with_: str | None = None
    ) -> Employee:
        params = _core.drop_query_none(
            {"any_sub_club": "1" if any_sub_club else None, "with": with_}
        )
        return await self._single(
            Employee,
            f"club/{self._club_id}/employee/{member_id}",
            params,
            f"Employee {member_id} was not found in the response",
        )

    async def create_employee(self, data: dict[str, Any]) -> Employee:
        return await self._mutate_employee(f"club/{self._club_id}/employee", data)

    async def update_employee(self, member_id: int, data: dict[str, Any]) -> Employee:
        return await self._mutate_employee(f"club/{self._club_id}/employee/{member_id}", data)

    async def create_or_update_employee(self, data: dict[str, Any]) -> Employee:
        return await self._mutate_employee(f"club/{self._club_id}/employee/create_or_update", data)

    async def members(
        self,
        *,
        sync_from: int = 0,
        club_member_id: int | None = None,
        rfid_tag: str | None = None,
        external_id: str | None = None,
        email: str | None = None,
        any_sub_club: bool = False,
        with_: str | None = None,
    ) -> AsyncIterator[list[Member]]:
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
        async for page in self._pages(
            Member, f"club/{self._club_id}/member", params, _core.advance_member_cursor
        ):
            yield page

    async def all_members(self, **kwargs: Any) -> list[Member]:
        return [member async for page in self.members(**kwargs) for member in page]

    async def member(
        self, member_id: int, *, any_sub_club: bool = False, with_: str | None = None
    ) -> Member:
        params = _core.drop_query_none(
            {"any_sub_club": "1" if any_sub_club else None, "with": with_}
        )
        return await self._single(
            Member,
            f"club/{self._club_id}/member/{member_id}",
            params,
            f"Member {member_id} was not found in the response",
        )

    async def create_member(self, data: dict[str, Any]) -> Member:
        return await self._mutate_member(f"club/{self._club_id}/member", data)

    async def update_member(self, member_id: int, data: dict[str, Any]) -> Member:
        return await self._mutate_member(f"club/{self._club_id}/member/{member_id}", data)

    async def create_or_update_member(self, data: dict[str, Any]) -> Member:
        return await self._mutate_member(f"club/{self._club_id}/member/create_or_update", data)

    async def activate_user(self, data: dict[str, Any]) -> ActivateUserResult:
        _, result = await self._request(
            "POST", f"club/{self._club_id}/member/activate_user", json=data
        )
        return ActivateUserResult.model_validate(result)

    async def events(
        self,
        *,
        sync_from: int = 0,
        timestamp_start: int | None = None,
        timestamp_end: int | None = None,
        member_id: int | None = None,
        schedule_id: int | None = None,
    ) -> AsyncIterator[list[ClubEvent]]:
        params = _core.drop_query_none(
            {
                "sync_from": sync_from,
                "timestamp_start": timestamp_start,
                "timestamp_end": timestamp_end,
                "member_id": member_id,
                "schedule_id": schedule_id,
            }
        )
        async for page in self._pages(
            ClubEvent, f"club/{self._club_id}/events", params, _core.advance_event_cursor
        ):
            yield page

    async def all_events(self, **kwargs: Any) -> list[ClubEvent]:
        return [event async for page in self.events(**kwargs) for event in page]

    async def event(self, event_id: str, *, sync_from: int = 0) -> ClubEvent:
        return await self._single(
            ClubEvent,
            f"club/{self._club_id}/events/{event_id}",
            {"sync_from": sync_from},
            f"Event {event_id} was not found in the response",
        )

    async def membership_instances(
        self, *, sync_from: int = 0, member_id: int | None = None
    ) -> AsyncIterator[list[MembershipInstance]]:
        params = _core.drop_query_none(
            {"sync_from": sync_from, "from_id": 0, "member_id": member_id}
        )
        async for page in self._pages(
            MembershipInstance,
            f"club/{self._club_id}/membership/instance",
            params,
            _core.advance_instance_cursor,
        ):
            yield page

    async def all_membership_instances(self, **kwargs: Any) -> list[MembershipInstance]:
        return [i async for page in self.membership_instances(**kwargs) for i in page]

    async def create_membership_instance(self, data: dict[str, Any]) -> MembershipContract:
        _, result = await self._request(
            "POST", f"club/{self._club_id}/membership/instance", json=data
        )
        return MembershipContract.model_validate(result)

    async def membership_definitions(
        self, *, sync_from: int = 0, status: str | None = None
    ) -> AsyncIterator[list[MembershipDefinition]]:
        params = _core.drop_query_none({"sync_from": sync_from, "status": status})
        async for page in self._pages(
            MembershipDefinition,
            f"club/{self._club_id}/membership/definition",
            params,
            _core.advance_page_param,
        ):
            yield page

    async def all_membership_definitions(self, **kwargs: Any) -> list[MembershipDefinition]:
        return [d async for page in self.membership_definitions(**kwargs) for d in page]

    async def event_participants(
        self,
        *,
        sync_from: int = 0,
        timestamp_start: int | None = None,
        timestamp_end: int | None = None,
        event_id: str | None = None,
        fill_guestname: bool = False,
    ) -> AsyncIterator[list[EventParticipant]]:
        params = _core.drop_query_none(
            {
                "sync_from": sync_from,
                "timestamp_start": timestamp_start,
                "timestamp_end": timestamp_end,
                "event_id": event_id,
                "fill_guestname": "1" if fill_guestname else None,
            }
        )
        async for page in self._pages(
            EventParticipant,
            f"club/{self._club_id}/eventparticipants",
            params,
            _core.advance_participant_cursor,
        ):
            yield page

    async def all_event_participants(self, **kwargs: Any) -> list[EventParticipant]:
        return [p async for page in self.event_participants(**kwargs) for p in page]

    async def event_participant(
        self, event_participant_id: int, *, sync_from: int = 0, fill_guestname: bool = False
    ) -> EventParticipant:
        params = _core.drop_query_none(
            {"sync_from": sync_from, "fill_guestname": "1" if fill_guestname else None}
        )
        return await self._single(
            EventParticipant,
            f"club/{self._club_id}/eventparticipants/{event_participant_id}",
            params,
            f"Event participant {event_participant_id} was not found in the response",
        )

    async def create_event_participant(self, data: dict[str, Any]) -> EventParticipantCreated:
        _, result = await self._request(
            "POST", f"club/{self._club_id}/eventparticipants", json=data
        )
        return EventParticipantCreated.model_validate(result)

    async def update_event_participant(
        self, event_participant_id: int, *, ticket_printed: bool
    ) -> None:
        await self._request(
            "PUT",
            f"club/{self._club_id}/eventparticipants",
            json={"event_participant_id": event_participant_id, "ticket_printed": ticket_printed},
        )

    async def delete_event_participant(self, event_participant_id: int) -> None:
        await self._request(
            "DELETE", f"club/{self._club_id}/eventparticipants/{event_participant_id}"
        )

    async def club_taxes(self) -> list[ClubTax]:
        _, result = await self._request("GET", f"club/{self._club_id}/club-taxes")
        return [ClubTax.model_validate(item) for item in result or []]

    async def income_categories(self) -> list[IncomeCategory]:
        _, result = await self._request("GET", f"club/{self._club_id}/income-categories")
        return [IncomeCategory.model_validate(item) for item in result or []]

    async def invoices(self) -> AsyncIterator[list[Invoice]]:
        async for page in self._pages(
            Invoice, f"club/{self._club_id}/invoices", {}, _core.advance_page_param
        ):
            yield page

    async def all_invoices(self) -> list[Invoice]:
        return [invoice async for page in self.invoices() for invoice in page]

    async def invoice(self, guid: str) -> Invoice:
        return await self._single(
            Invoice,
            f"club/{self._club_id}/invoices/{guid}",
            {},
            f"Invoice {guid} was not found in the response",
        )

    async def create_invoice(self, data: dict[str, Any]) -> Invoice:
        _, result = await self._request("POST", f"club/{self._club_id}/invoices", json=data)
        return Invoice.model_validate(result)

    async def visits(
        self, *, sync_from: int = 0, member_id: int | None = None
    ) -> AsyncIterator[list[Visit]]:
        params = _core.drop_query_none({"sync_from": sync_from, "member_id": member_id})
        async for page in self._pages(
            Visit, f"club/{self._club_id}/visits", params, _core.advance_visit_cursor
        ):
            yield page

    async def all_visits(self, **kwargs: Any) -> list[Visit]:
        return [visit async for page in self.visits(**kwargs) for visit in page]

    async def visit(self, visit_id: int) -> Visit:
        return await self._single(
            Visit,
            f"club/{self._club_id}/visits/{visit_id}",
            {},
            f"Visit {visit_id} was not found in the response",
        )

    async def create_visit(self, data: dict[str, Any]) -> VisitRegistered:
        _, result = await self._request("POST", f"club/{self._club_id}/visits", json=data)
        return VisitRegistered.model_validate(result)

    async def member_notes(
        self, *, sync_from: int = 0, member_id: int | None = None, note_type: str | None = None
    ) -> list[MemberNote]:
        params = _core.drop_query_none(
            {"sync_from": sync_from, "member_id": member_id, "note_type": note_type}
        )
        _, result = await self._request("GET", f"club/{self._club_id}/notes", params=params)
        return [MemberNote.model_validate(item) for item in result or []]

    async def member_note(self, note_id: int) -> MemberNote:
        return await self._single(
            MemberNote,
            f"club/{self._club_id}/notes/{note_id}",
            {"sync_from": 0},
            f"Note {note_id} was not found in the response",
        )

    async def create_member_note(self, data: dict[str, Any]) -> MemberNoteCreated:
        _, result = await self._request("POST", f"club/{self._club_id}/notes", json=data)
        return MemberNoteCreated.model_validate(result)

    async def update_member_note(
        self, note_id: int, *, note_text: str | None = None, note_type: str | None = None
    ) -> None:
        if note_text is None and note_type is None:
            raise ValueError("At least one of note_text / note_type must be given.")
        body = _core.drop_query_none(
            {"note_id": note_id, "note_text": note_text, "note_type": note_type}
        )
        await self._request("PUT", f"club/{self._club_id}/notes", json=body)

    async def delete_member_note(self, note_id: int) -> None:
        await self._request("DELETE", f"club/{self._club_id}/notes/{note_id}")

    async def member_credits(
        self, *, sync_from: int = 0, member_id: int | None = None
    ) -> AsyncIterator[list[MemberCredit]]:
        params = _core.drop_query_none({"sync_from": sync_from, "member_id": member_id})
        seen: set[str] = set()
        async for page in self._pages(
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

    async def all_member_credits(self, **kwargs: Any) -> list[MemberCredit]:
        return [credit async for page in self.member_credits(**kwargs) for credit in page]

    async def add_member_credits(self, data: dict[str, Any]) -> CreditTransaction:
        _, result = await self._request("PUT", f"club/{self._club_id}/credit", json=data)
        return CreditTransaction.model_validate(result)

    async def assign_workout(self, data: dict[str, Any]) -> None:
        await self._request("POST", f"club/{self._club_id}/member/workouts", json=data)

    async def bodymetrics(
        self, member_id: int, *, sync_from: int = 0, type: str | None = None
    ) -> list[Bodymetric]:
        params = _core.drop_query_none(
            {"sync_from": sync_from, "member_id": member_id, "type": type}
        )
        _, result = await self._request("GET", f"club/{self._club_id}/bodymetrics", params=params)
        return [Bodymetric.model_validate(item) for item in result or []]

    async def bodymetric(self, bodymetric_id: int, member_id: int) -> Bodymetric:
        return await self._single(
            Bodymetric,
            f"club/{self._club_id}/bodymetrics/{bodymetric_id}",
            {"member_id": member_id},
            f"Bodymetric {bodymetric_id} was not found in the response",
        )

    async def update_bodymetric(self, data: dict[str, Any]) -> BodymetricUpdated:
        _, result = await self._request("PUT", f"club/{self._club_id}/bodymetrics", json=data)
        return BodymetricUpdated.model_validate(result)

    # ── Internals ──────────────────────────────────────────────────────

    async def _pages(
        self,
        model: type[_M],
        path: str,
        params: _core.Params,
        advance: _core.Advance,
    ) -> AsyncIterator[list[_M]]:
        while True:
            status, result = await self._request("GET", path, params=params)
            rows = result if isinstance(result, list) else []
            items = [model.model_validate(row) for row in rows]
            if items:
                yield items
            next_params = advance(status, rows[-1] if rows else None, params)
            if next_params is None:
                return
            params = next_params

    async def _single(self, model: type[_M], path: str, params: _core.Params, not_found: str) -> _M:
        _, result = await self._request("GET", path, params=params)
        rows = _core.wrap_list(result)
        if not rows:
            raise VirtuaGymApiError(420, not_found)
        return model.model_validate(rows[0])

    async def _mutate_member(self, path: str, data: dict[str, Any]) -> Member:
        _, result = await self._request("PUT", path, json=data)
        member_id = _extract_member_id(result)
        try:
            return await self.member(member_id)
        except VirtuaGymApiError:
            return await self.member(member_id, any_sub_club=True)

    async def _mutate_employee(self, path: str, data: dict[str, Any]) -> Employee:
        _, result = await self._request("PUT", path, json=data)
        return await self.employee(_extract_member_id(result))

    async def _request(
        self,
        method: str,
        path: str,
        params: _core.Params | None = None,
        json: Any = None,
    ) -> tuple[_core.Status, Any]:
        query = dict(params or {})
        query["api_key"] = self._api_key
        query["club_secret"] = self._club_secret
        response = await self._http.request(
            method, f"{_core.BASE_URL}/{path}", params=query, json=json
        )
        if response.is_error:
            error = _core.error_from_http_status(response)
            if error is not None:
                raise error
            response.raise_for_status()
        return _core.parse_envelope(response)
