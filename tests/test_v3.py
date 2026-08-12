from typing import Any

import pytest
import respx
from httpx import Response

from virtuagym import AsyncVirtuaGymClientV3, VirtuaGymClientV3, VirtuaGymV3ApiError

TOKEN_URL = "https://iam.services.virtuagym.com/auth/realms/virtuagym/protocol/openid-connect/token"
GATEWAY = "https://gateway.services.virtuagym.com"


def client() -> VirtuaGymClientV3:
    return VirtuaGymClientV3("test-client-id", "test-client-secret", 12345)


def token_response(access_token: str = "test-token") -> Response:
    return Response(200, json={"access_token": access_token, "expires_in": 1800})


def lead(lead_id: str) -> dict[str, Any]:
    return {
        "lead_id": lead_id,
        "lead_guid": f"guid-{lead_id}",
        "club_id": "12345",
        "status_id": "1",
        "source_id": "2",
        "owner_id": "0",
        "firstname": "Jane",
        "lastname": "Doe",
        "email": "jane.doe@example.com",
        "phone": "",
        "mobile": "",
        "gender": "",
        "birthday": None,
        "address": "",
        "address_2": "",
        "zip_code": "",
        "city": "",
        "state": "",
        "country": "",
        "language": "",
        "picture": "",
        "converted_to_member_id": "0",
        "external_id": "",
        "lead_since": "2026-08-01",
        "created_by_user_id": "100",
        "edited_by_user_id": "100",
        "deleted": "0",
        "timestamp_created": "1785836412",
        "timestamp_edited": "1786448091",
        "inactive": "0",
    }


def leads_envelope(leads: list[dict[str, Any]], **extra: Any) -> Response:
    return Response(
        200, json={"status": "success", "message": "", "data": {"leads": leads, **extra}}
    )


def event(event_id: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "datetime_start": 1786500000000,
        "datetime_end": 1786503600000,
    }


def events_envelope(events: list[dict[str, Any]], total_pages: int = 1) -> Response:
    return Response(
        200,
        json={
            "status": "success",
            "status_code": 200,
            "data": {"events": events, "total_pages": total_pages},
        },
    )


@respx.mock
def test_requests_client_credentials_token_with_club_header() -> None:
    token_route = respx.post(TOKEN_URL).mock(return_value=token_response())
    api_route = respx.get(f"{GATEWAY}/v3/clubs/12345/leads").mock(return_value=leads_envelope([]))

    client().all_leads()

    token_request = token_route.calls[0].request
    assert token_request.headers["x-represent-club-id"] == "12345"
    body = token_request.content.decode()
    assert "client_id=test-client-id" in body
    assert "grant_type=client_credentials" in body
    api_request = api_route.calls[0].request
    assert api_request.headers["Authorization"] == "Bearer test-token"
    assert api_request.url.params["page"] == "1"
    assert api_request.url.params["limit"] == "100"


@respx.mock
def test_reuses_cached_token() -> None:
    token_route = respx.post(TOKEN_URL).mock(return_value=token_response())
    respx.get(f"{GATEWAY}/v3/clubs/12345/leads").mock(return_value=leads_envelope([]))

    c = client()
    c.all_leads()
    c.all_leads()

    assert token_route.call_count == 1


@respx.mock
def test_refreshes_token_and_retries_once_on_401() -> None:
    respx.post(TOKEN_URL).mock(
        side_effect=[token_response("stale-token"), token_response("fresh-token")]
    )
    api_route = respx.get(f"{GATEWAY}/v3/clubs/12345/leads").mock(
        side_effect=[
            Response(401, json={"message": "Token not valid.", "status": "fail"}),
            leads_envelope([lead("1")]),
        ]
    )

    leads = client().all_leads()

    assert len(leads) == 1
    assert api_route.calls[1].request.headers["Authorization"] == "Bearer fresh-token"


@respx.mock
def test_does_not_retry_second_consecutive_401() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    respx.get(f"{GATEWAY}/v3/clubs/12345/leads").mock(
        return_value=Response(401, json={"message": "Token not valid.", "status": "fail"})
    )

    with pytest.raises(VirtuaGymV3ApiError) as exc:
        client().all_leads()
    assert exc.value.http_status == 401


@respx.mock
def test_surfaces_token_endpoint_errors() -> None:
    respx.post(TOKEN_URL).mock(
        return_value=Response(
            401,
            json={
                "error": "invalid_client",
                "error_description": "Invalid client or Invalid client credentials",
            },
        )
    )

    with pytest.raises(VirtuaGymV3ApiError, match="Invalid client"):
        client().all_leads()


@respx.mock
def test_follows_leads_pagination_until_short_page() -> None:
    route = respx.get(f"{GATEWAY}/v3/clubs/12345/leads").mock(
        side_effect=[
            leads_envelope([lead("1"), lead("2")]),
            leads_envelope([lead("3")]),
        ]
    )
    respx.post(TOKEN_URL).mock(return_value=token_response())

    leads = client().all_leads(limit=2)

    assert [x.lead_id for x in leads] == ["1", "2", "3"]
    assert route.calls[0].request.url.params["page"] == "1"
    assert route.calls[1].request.url.params["page"] == "2"


@respx.mock
def test_tolerates_owners_map_as_empty_array() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    respx.get(f"{GATEWAY}/v3/clubs/12345/leads").mock(
        return_value=leads_envelope([lead("1")], has_leads=True, owners=[])
    )

    assert len(client().all_leads()) == 1


@respx.mock
def test_retrieves_single_lead_and_maps_nested_error() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    respx.get(f"{GATEWAY}/v3/clubs/12345/leads/7").mock(
        return_value=Response(
            200,
            json={"status": "success", "data": {"name": "Lead Detail", "lead": lead("7")}},
        )
    )
    respx.get(f"{GATEWAY}/v3/clubs/12345/leads/1").mock(
        return_value=Response(
            404,
            json={
                "status": "fail",
                "error": {"status": "error", "message": "ERROR: Lead not found"},
            },
        )
    )

    assert client().lead(7).lead_id == "7"
    with pytest.raises(VirtuaGymV3ApiError, match="ERROR: Lead not found") as exc:
        client().lead(1)
    assert exc.value.http_status == 404


@respx.mock
def test_creates_lead_and_refetches_canonical_record() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    post = respx.post(f"{GATEWAY}/v3/clubs/12345/leads").mock(
        # Create returns the id as a string; update as a number.
        return_value=Response(
            200,
            json={
                "status": "success",
                "data": {"status": "success", "message": "Lead created", "id": "99"},
            },
        )
    )
    respx.get(f"{GATEWAY}/v3/clubs/12345/leads/99").mock(
        return_value=Response(
            200,
            json={"status": "success", "data": {"name": "Lead Detail", "lead": lead("99")}},
        )
    )

    created = client().create_lead(
        {"firstname": "Jane", "lastname": "Doe", "email": "jane.doe@example.com"}
    )

    assert created.lead_id == "99"
    assert post.called


@respx.mock
def test_retrieves_schedule_events_and_follows_total_pages() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    route = respx.get(f"{GATEWAY}/private/v3/clubs/12345/schedule/integration/events").mock(
        side_effect=[events_envelope([event("e-1")], 2), events_envelope([event("e-2")], 2)]
    )

    events = client().all_events(date_start=1786500000000, date_end=1786600000000)

    assert [e.event_id for e in events] == ["e-1", "e-2"]
    first = route.calls[0].request.url.params
    assert first["date_start"] == "1786500000000"
    assert first["page_size"] == "100"
    assert route.calls[1].request.url.params["page"] == "2"


@respx.mock
def test_treats_204_bookings_response_as_empty() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    respx.get(f"{GATEWAY}/private/v3/clubs/12345/schedule/integration/events/bookings").mock(
        return_value=Response(204)
    )

    assert client().all_event_bookings(date_start=1, date_end=2) == []


@respx.mock
def test_creates_booking_and_returns_attempts() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    respx.post(f"{GATEWAY}/private/v3/clubs/12345/schedule/integration/events/e-42/bookings").mock(
        return_value=Response(
            200,
            json={
                "status": "accept",
                "status_code": 200,
                "bookings": [
                    {
                        "booked": True,
                        "day": "2026-08-16",
                        "reason": 2,
                        "time_start": "13:00:00",
                        "time_end": "14:00:00",
                    }
                ],
                "total_bookings": 1,
            },
        )
    )

    result = client().create_booking("e-42", {"member_id": 7})

    assert result.total_bookings == 1
    assert result.bookings[0].booked is True
    assert result.bookings[0].reason == 2


@respx.mock
def test_cancels_booking_with_rule_and_refund_flags() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    route = respx.delete(
        f"{GATEWAY}/private/v3/clubs/12345/schedule/integration/events/e-42/bookings"
    ).mock(return_value=Response(200, json={"status": "success", "status_code": 200}))

    client().cancel_booking(
        "e-42", member_id=7, refund=False, free_cancellation_range=False, cancellation_range=True
    )

    params = route.calls[0].request.url.params
    assert params["member_id"] == "7"
    assert params["refund"] == "false"
    assert params["free_cancellation_range"] == "false"
    assert params["cancellation_range"] == "true"


@respx.mock
def test_surfaces_schedule_errors_with_fields() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    respx.get(f"{GATEWAY}/private/v3/clubs/12345/schedule/integration/events").mock(
        return_value=Response(
            400, json={"message": "Invalid request", "fields": ["date_start"], "status": "fail"}
        )
    )

    with pytest.raises(VirtuaGymV3ApiError) as exc:
        client().all_events(date_start=1, date_end=2)
    assert exc.value.http_status == 400
    assert exc.value.fields == ["date_start"]


@respx.mock
async def test_async_client_mirrors_sync_behavior() -> None:
    respx.post(TOKEN_URL).mock(return_value=token_response())
    respx.get(f"{GATEWAY}/v3/clubs/12345/leads").mock(
        side_effect=[leads_envelope([lead("1"), lead("2")]), leads_envelope([lead("3")])]
    )
    async_client = AsyncVirtuaGymClientV3("test-client-id", "test-client-secret", 12345)

    leads = await async_client.all_leads(limit=2)

    assert [x.lead_id for x in leads] == ["1", "2", "3"]
