from typing import Any

import pydantic
import pytest
import respx
from httpx import Response

from virtuagym import AsyncVirtuaGymClientV1, VirtuaGymApiError, VirtuaGymClientV1

BASE = "https://api.virtuagym.com/api/v1"


def client() -> VirtuaGymClientV1:
    return VirtuaGymClientV1("test-api-key", "test-club-secret", 12345)


def employee(member_id: int, timestamp_edit: int) -> dict[str, Any]:
    return {
        "member_id": member_id,
        "club_id": 12345,
        "firstname": "Jane",
        "lastname": "Doe",
        "email": "jane.doe@example.com",
        "active": True,
        "is_pro": False,
        "member_since": 1700000000000,
        "timestamp_edit": timestamp_edit,
    }


def envelope(result: Any, results_remaining: int = 0, **extra: Any) -> dict[str, Any]:
    return {
        "status": {
            "statuscode": 200,
            "statusmessage": "Everything OK",
            "result_count": len(result) if isinstance(result, list) else 1,
            "timestamp": 1785274537785,
            "results_remaining": results_remaining,
            **extra,
        },
        "result": result,
    }


@respx.mock
def test_retrieves_employees_with_credentials_in_url() -> None:
    route = respx.get(f"{BASE}/club/12345/employee").mock(
        return_value=Response(200, json=envelope([employee(1, 100)]))
    )

    employees = client().all_employees()

    assert len(employees) == 1
    assert employees[0].member_id == 1
    params = route.calls[0].request.url.params
    assert params["api_key"] == "test-api-key"
    assert params["club_secret"] == "test-club-secret"
    assert params["sync_from"] == "0"


@respx.mock
def test_follows_next_page_cursor_while_results_remain() -> None:
    route = respx.get(f"{BASE}/club/12345/employee").mock(
        side_effect=[
            Response(
                200,
                json=envelope(
                    [employee(1, 100), employee(2, 200)],
                    1,
                    next_page="sync_from=200&from_id=2",
                ),
            ),
            Response(200, json=envelope([employee(3, 300)], 0)),
        ]
    )

    employees = client().all_employees()

    assert [e.member_id for e in employees] == [1, 2, 3]
    second = route.calls[1].request.url.params
    assert second["sync_from"] == "200"
    assert second["from_id"] == "2"


@respx.mock
def test_falls_back_to_last_row_cursor_without_next_page() -> None:
    route = respx.get(f"{BASE}/club/12345/employee").mock(
        side_effect=[
            Response(200, json=envelope([employee(1, 100)], 1)),
            Response(200, json=envelope([], 0)),
        ]
    )

    client().all_employees()

    second = route.calls[1].request.url.params
    assert second["sync_from"] == "100"
    assert second["from_id"] == "1"


@respx.mock
def test_collapses_member_edited_mid_walk_into_latest_copy() -> None:
    # Member 1 is edited between pages, moves past the cursor and comes back.
    respx.get(f"{BASE}/club/12345/member").mock(
        side_effect=[
            Response(
                200,
                json=envelope(
                    [employee(1, 100), employee(2, 200)], 1, next_page="sync_from=200&from_id=2"
                ),
            ),
            Response(200, json=envelope([employee(3, 300), employee(1, 400)], 0)),
        ]
    )

    members = client().all_members()

    assert [m.member_id for m in members] == [1, 2, 3]
    assert members[0].timestamp_edit == 400


@respx.mock
def test_collapses_employee_edited_mid_walk_into_latest_copy() -> None:
    respx.get(f"{BASE}/club/12345/employee").mock(
        side_effect=[
            Response(200, json=envelope([employee(1, 100)], 1)),
            Response(200, json=envelope([employee(1, 200)], 0)),
        ]
    )

    employees = client().all_employees()

    assert len(employees) == 1
    assert employees[0].timestamp_edit == 200


@respx.mock
def test_raises_on_flat_in_band_error_with_http_200() -> None:
    respx.get(f"{BASE}/club/12345/employee").mock(
        return_value=Response(200, json={"statuscode": 420, "statusmessage": "Not found."})
    )

    with pytest.raises(VirtuaGymApiError) as exc:
        client().all_employees()
    assert exc.value.statuscode == 420
    assert "Not found." in str(exc.value)


@respx.mock
def test_raises_on_nested_error_with_validation_errors() -> None:
    respx.post(f"{BASE}/club/12345/member/activate_user").mock(
        return_value=Response(
            200,
            json={
                "status": {
                    "statuscode": 400,
                    "statusmessage": "Validation failed",
                    "result_count": 0,
                    "timestamp": 1,
                },
                "errors": {"email": "invalid"},
            },
        )
    )

    with pytest.raises(VirtuaGymApiError) as exc:
        client().activate_user({"email": "nope"})
    assert exc.value.statuscode == 400
    assert exc.value.errors == {"email": "invalid"}


@respx.mock
def test_maps_real_http_error_codes_to_api_error() -> None:
    respx.get(f"{BASE}/club/12345/bodymetrics").mock(
        return_value=Response(
            404, json={"statuscode": 404, "statusmessage": "Member not found in club"}
        )
    )

    with pytest.raises(VirtuaGymApiError) as exc:
        client().bodymetrics(1)
    assert exc.value.statuscode == 404


@respx.mock
def test_normalizes_flat_success_envelope() -> None:
    respx.get(f"{BASE}/club/12345/bodymetrics").mock(
        return_value=Response(
            200,
            json={
                "statuscode": 200,
                "statusmessage": "OK",
                "result": [{"id": 7, "type": "weight", "value": 80.5, "timestamp": 1700000000}],
            },
        )
    )

    metrics = client().bodymetrics(1)

    assert metrics[0].id == 7
    assert metrics[0].value == 80.5


@respx.mock
def test_refetches_canonical_member_after_mutation() -> None:
    member = {
        "member_id": 42,
        "club_id": 12345,
        "firstname": "John",
        "lastname": "Doe",
        "email": "john@example.com",
        "active": True,
        "is_pro": False,
        "member_since": 1700000000000,
        "timestamp_edit": 100,
    }
    put = respx.put(f"{BASE}/club/12345/member").mock(
        # PUT response with inconsistent types; only member_id is trusted.
        return_value=Response(
            200, json=envelope({"member_id": 42, "active": 1, "member_since": "2015-01-14"})
        )
    )
    get = respx.get(f"{BASE}/club/12345/member/42").mock(
        return_value=Response(200, json=envelope([member]))
    )

    result = client().create_member({"firstname": "John", "lastname": "Doe"})

    assert result.member_id == 42
    assert result.active is True
    assert put.called and get.called


@respx.mock
def test_raises_420_when_single_member_missing() -> None:
    respx.get(f"{BASE}/club/12345/member/999").mock(return_value=Response(200, json=envelope([])))

    with pytest.raises(VirtuaGymApiError, match="Member 999 was not found"):
        client().member(999)


def instance(instance_id: int, **flags: Any) -> dict[str, Any]:
    return {
        "instance_id": instance_id,
        "member_id": 42,
        "membership_id": 7,
        "active": flags.get("active", True),
        "cancelled": flags.get("cancelled", False),
        "contract_autorenewed": False,
        "completed": False,
        "paused": False,
        "stopped": flags.get("stopped", False),
        "start_date": "2026-01-01",
        "contract_start_date": "2026-01-01",
        "contract_end_date": "2026-12-31",
        "membership_name": "Gold",
    }


@respx.mock
def test_normalizes_01_membership_flags_to_booleans() -> None:
    respx.get(f"{BASE}/club/12345/membership/instance").mock(
        return_value=Response(200, json=envelope([instance(1, active=1, cancelled=0, stopped=1)]))
    )

    instances = client().all_membership_instances()

    assert instances[0].active is True
    assert instances[0].cancelled is False
    assert instances[0].stopped is True


@respx.mock
def test_pages_membership_instances_on_inclusive_from_id() -> None:
    route = respx.get(f"{BASE}/club/12345/membership/instance").mock(
        side_effect=[
            Response(200, json=envelope([instance(10)], 1)),
            Response(200, json=envelope([instance(11)], 0)),
        ]
    )

    instances = client().all_membership_instances()

    assert len(instances) == 2
    assert route.calls[0].request.url.params["from_id"] == "0"
    assert route.calls[1].request.url.params["from_id"] == "11"


def credit(member_id: int, edited: int) -> dict[str, Any]:
    return {
        "club_id": 12345,
        "member_id": member_id,
        "service_type": "access",
        "credit_amount": 20,
        "credit_unlimited": False,
        "timestamp_created": 1456499187,
        "timestamp_edited": edited,
    }


@respx.mock
def test_drops_credit_rows_repeated_on_boundary_ties() -> None:
    respx.get(f"{BASE}/club/12345/credit").mock(
        side_effect=[
            Response(
                200,
                json=envelope([credit(1, 100), credit(2, 200)], 1, next_page="sync_from=200"),
            ),
            Response(200, json=envelope([credit(2, 200), credit(3, 300)], 0)),
        ]
    )

    credits = client().all_member_credits()

    assert [c.member_id for c in credits] == [1, 2, 3]


@respx.mock
def test_retrieves_single_invoice_returned_as_bare_object() -> None:
    invoice = {
        "guid": "abc-123",
        "club_id": 12345,
        "name": "Invoice 1",
        "price": 12.5,
        "price_ex_vat": 10.33,
        "currency": "EUR",
        "paid": False,
        "amount_due": 12.5,
        "deleted": False,
        "timestamp": 1700000000,
        "timestamp_edit": 1700000000,
        "timestamp_created": 1700000000,
        "rows": [],
    }
    respx.get(f"{BASE}/club/12345/invoices/abc-123").mock(
        return_value=Response(200, json=envelope(invoice))
    )

    result = client().invoice("abc-123")

    assert result.guid == "abc-123"


@respx.mock
def test_fails_loudly_on_schema_mismatch() -> None:
    respx.get(f"{BASE}/club/12345/employee").mock(
        return_value=Response(200, json=envelope([{"nonsense": True}]))
    )

    with pytest.raises(pydantic.ValidationError):
        client().all_employees()


@respx.mock
def test_coerces_mixed_type_ids() -> None:
    respx.get(f"{BASE}/club/12345/club-taxes").mock(
        return_value=Response(
            200,
            json=envelope(
                [{"club_tax_id": 1, "tax_id": 42, "tax_name": "BTW 21%", "tax_perc": "21.00"}]
            ),
        )
    )

    taxes = client().club_taxes()

    assert taxes[0].tax_id == "42"
    assert taxes[0].tax_perc == "21.00"


@respx.mock
async def test_async_client_mirrors_sync_behavior() -> None:
    respx.get(f"{BASE}/club/12345/employee").mock(
        side_effect=[
            Response(200, json=envelope([employee(1, 100)], 1)),
            Response(200, json=envelope([employee(2, 200)], 0)),
        ]
    )
    async_client = AsyncVirtuaGymClientV1("test-api-key", "test-club-secret", 12345)

    employees = await async_client.all_employees()

    assert [e.member_id for e in employees] == [1, 2]


@respx.mock
async def test_async_client_collapses_member_edited_mid_walk() -> None:
    respx.get(f"{BASE}/club/12345/member").mock(
        side_effect=[
            Response(200, json=envelope([employee(1, 100)], 1)),
            Response(200, json=envelope([employee(1, 200)], 0)),
        ]
    )
    async_client = AsyncVirtuaGymClientV1("test-api-key", "test-club-secret", 12345)

    members = await async_client.all_members()

    assert len(members) == 1
    assert members[0].timestamp_edit == 200
