"""Read-only smoke tests against the live Virtuagym API.

Run with ``pytest -m smoke``; requires credentials in ``.env``.
"""

import time

import pytest
from conftest import require_env

from virtuagym import AsyncVirtuaGymClientV3, VirtuaGymClientV1, VirtuaGymClientV3

pytestmark = pytest.mark.smoke


@pytest.fixture()
def v1() -> VirtuaGymClientV1:
    return VirtuaGymClientV1(
        api_key=require_env("VIRTUAGYM_API_KEY"),
        club_secret=require_env("VIRTUAGYM_CLUB_SECRET"),
        club_id=int(require_env("VIRTUAGYM_CLUB_ID")),
    )


@pytest.fixture()
def v3() -> VirtuaGymClientV3:
    return VirtuaGymClientV3(
        client_id=require_env("VIRTUAGYM_CLIENT_ID"),
        client_secret=require_env("VIRTUAGYM_CLIENT_SECRET"),
        club_id=int(require_env("VIRTUAGYM_CLUB_ID")),
    )


def test_retrieves_employees(v1: VirtuaGymClientV1) -> None:
    for employee in v1.all_employees():
        assert employee.member_id > 0
        assert employee.firstname


def test_retrieves_all_members_without_duplicates(v1: VirtuaGymClientV1) -> None:
    members = v1.all_members()

    assert members
    ids = [m.member_id for m in members]
    assert len(set(ids)) == len(ids)


def test_retrieves_single_member_with_memberships(v1: VirtuaGymClientV1) -> None:
    first = next(iter(v1.members()))[0]

    single = v1.member(first.member_id, with_="memberships")

    assert single.member_id == first.member_id
    assert isinstance(single.memberships, list)


def test_retrieves_membership_instances_without_duplicates(v1: VirtuaGymClientV1) -> None:
    instances = v1.all_membership_instances()

    ids = [i.instance_id for i in instances]
    assert len(set(ids)) == len(ids)
    assert all(isinstance(i.active, bool) for i in instances)


def test_retrieves_membership_definitions_without_duplicates(v1: VirtuaGymClientV1) -> None:
    definitions = v1.all_membership_definitions()

    ids = [d.membership_id for d in definitions]
    assert len(set(ids)) == len(ids)


def test_retrieves_event_participants(v1: VirtuaGymClientV1) -> None:
    # Default window: (today - 1 month) .. (today + 1 month).
    assert isinstance(v1.all_event_participants(), list)


def test_retrieves_club_taxes_and_income_categories(v1: VirtuaGymClientV1) -> None:
    for tax in v1.club_taxes():
        assert isinstance(tax.tax_id, str)
    for category in v1.income_categories():
        assert isinstance(category.income_category_id, str)


def test_retrieves_first_page_of_invoices(v1: VirtuaGymClientV1) -> None:
    page = next(iter(v1.invoices()), [])
    for invoice in page:
        assert invoice.guid
        assert isinstance(invoice.rows, list)


def test_retrieves_member_credits_without_duplicates(v1: VirtuaGymClientV1) -> None:
    credits = v1.all_member_credits()

    keys = [f"{c.member_id}|{c.service_type}" for c in credits]
    assert len(set(keys)) == len(keys)


def test_retrieves_visits(v1: VirtuaGymClientV1) -> None:
    assert isinstance(v1.all_visits(), list)


def test_retrieves_member_notes(v1: VirtuaGymClientV1) -> None:
    for note in v1.member_notes():
        assert note.note_id > 0


def test_retrieves_all_leads_without_duplicates(v3: VirtuaGymClientV3) -> None:
    leads = v3.all_leads()

    assert leads
    ids = [lead.lead_id for lead in leads]
    assert len(set(ids)) == len(ids)


def test_paginates_leads_consistently(v3: VirtuaGymClientV3) -> None:
    by_default = sorted(lead.lead_id for lead in v3.all_leads())
    by_small_pages = sorted(lead.lead_id for lead in v3.all_leads(limit=10))

    assert by_small_pages == by_default


def test_retrieves_single_lead(v3: VirtuaGymClientV3) -> None:
    first = next(iter(v3.leads(limit=1)))[0]

    single = v3.lead(first.lead_id)

    assert single.lead_id == first.lead_id
    assert single.lead_guid == first.lead_guid


# The schedule tests require the schedule integration scope
# (schedule_public_api_club_<club_id>) on the OAuth client.


def _window() -> tuple[int, int]:
    now = int(time.time() * 1000)
    week = 7 * 24 * 3600 * 1000
    return now - week, now + week


def test_retrieves_schedule_events_without_duplicate_occurrences(v3: VirtuaGymClientV3) -> None:
    date_start, date_end = _window()

    events = v3.all_events(date_start=date_start, date_end=date_end)

    assert events
    # event_id repeats for occurrences of recurring events; the occurrence
    # (event_id + start time) must be unique.
    keys = [f"{e.event_id}|{e.datetime_start}" for e in events]
    assert len(set(keys)) == len(keys)


def test_retrieves_single_schedule_event(v3: VirtuaGymClientV3) -> None:
    date_start, date_end = _window()
    first = next(iter(v3.events(date_start=date_start, date_end=date_end)))[0]

    single = v3.event(first.event_id)

    assert single.event_id == first.event_id


def test_retrieves_event_bookings(v3: VirtuaGymClientV3) -> None:
    date_start, date_end = _window()

    # A 204 (no bookings) yields an empty list; both are valid.
    for event in v3.all_event_bookings(date_start=date_start, date_end=date_end):
        assert event.event_id
        for participant in event.participants or []:
            assert participant.member_id > 0


async def test_async_v3_client_against_live_api() -> None:
    client = AsyncVirtuaGymClientV3(
        client_id=require_env("VIRTUAGYM_CLIENT_ID"),
        client_secret=require_env("VIRTUAGYM_CLIENT_SECRET"),
        club_id=int(require_env("VIRTUAGYM_CLUB_ID")),
    )

    leads = await client.all_leads()

    assert leads
