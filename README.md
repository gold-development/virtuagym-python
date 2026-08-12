# virtuagym

[![CI](https://github.com/gold-development/virtuagym-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gold-development/virtuagym-python/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/virtuagym)](https://pypi.org/project/virtuagym/)

A typed Python client for the [Virtuagym API](https://github.com/virtuagym/api-documentation) — v1 (api key + club secret) and v3 (OAuth client credentials) — with sync and async clients.

- **Typed models** — every response is validated onto frozen [pydantic](https://docs.pydantic.dev) models: responses that don't match the schema fail loudly instead of corrupting your data.
- **Battle-tested against the live API** — the behavior of every endpoint (pagination cursors, envelope quirks, type inconsistencies) was verified live; see [API-FINDINGS](https://github.com/gold-development/virtuagym-node/blob/main/API-FINDINGS.md) for everything the docs don't tell you.
- **Pagination handled** — iterate lazily page by page, or fetch everything with one call. Duplicate rows caused by the API's inclusive cursors are deduplicated for you.
- **Sync and async** — `VirtuaGymClientV1`/`VirtuaGymClientV3` on httpx's sync client, `AsyncVirtuaGymClientV1`/`AsyncVirtuaGymClientV3` on its async client, identical method surfaces.
- Sibling packages: [Node.js/TypeScript](https://github.com/gold-development/virtuagym-node) and [PHP](https://github.com/gold-development/virtuagym-php).

## Installation

```bash
pip install virtuagym
```

Requires Python 3.10+.

## API v1 (api key + club secret)

You need three values, all found in Virtuagym under **Business settings → Business Info → Advanced**: your API key, the "Club Key" (club secret), and your club id.

```python
from virtuagym import VirtuaGymClientV1

client = VirtuaGymClientV1(
    api_key="...",
    club_secret="...",
    club_id=12345,
)

# Lazily, page by page — each HTTP request only happens when you ask for the next page
for page in client.members():
    print(f"received {len(page)} members")

# Or collect every page into a single list
members = client.all_members()

# Incremental sync (timestamp in ms)
changed = client.all_members(sync_from=last_sync_timestamp)

# Single member with membership instances embedded
member = client.member(7302399, with_="memberships")

# Mutations re-fetch and return the canonical record
created = client.create_member(
    {"firstname": "John", "lastname": "Doe", "email": "john@example.com"}
)
updated = client.update_member(created.member_id, {"gender": "f"})
upserted = client.create_or_update_member(
    {"external_id": "1ABC234567", "firstname": "John", "lastname": "Doe"}
)
```

The full v1 surface: `employees`, `members`, `activate_user`, `events`, `membership_instances` / `membership_definitions` / `create_membership_instance`, `event_participants` (bookings), `club_taxes`, `income_categories`, `invoices`, `visits`, `member_notes`, `member_credits` / `add_member_credits`, `assign_workout`, `bodymetrics`. Every list endpoint has a lazy iterator (`members()`) and a collector (`all_members()`). Mutation payloads are plain dicts with the API's wire-format keys.

Worth knowing (all verified live): single-resource GETs 404 with statuscode **420**; the notes endpoint is capped at the newest 500 rows; notes and credits use **seconds** for `sync_from` while most endpoints use milliseconds; credits rows have no unique id and page-boundary duplicates are deduplicated for you.

## API v3 (OAuth)

The v3 API is a separate stack behind `gateway.services.virtuagym.com`, authenticated with OAuth client credentials ([register via api@virtuagym.com](https://github.com/virtuagym/api-documentation/blob/master/V3_AUTHENTICATION.md)). Tokens are requested and renewed automatically (club-bound, ~30 min lifetime). Which v3 resources you can reach depends on the scopes Virtuagym registered for your client — without the right scope the API answers a misleading 401 `Token not valid.`.

```python
import time

from virtuagym import VirtuaGymClientV3

client = VirtuaGymClientV3(
    client_id="...",
    client_secret="...",
    club_id=12345,
)

# Leads — the live API serializes EVERY lead field as a string
leads = client.all_leads()
lead = client.lead(751563)
created = client.create_lead({"firstname": "Jane", "lastname": "Doe", "email": "jane@example.com"})
client.update_lead(created.lead_id, {"status_id": 12})  # Closed won

# Schedule (requires the schedule_public_api_club_<club_id> scope)
now = int(time.time() * 1000)
week = 7 * 24 * 3600 * 1000

events = client.all_events(date_start=now, date_end=now + week, event_type="appointment")
bookings = client.all_event_bookings(date_start=now, date_end=now + week, member_id=42)

result = client.create_booking(events[0].event_id, {"member_id": 42})
# Inspect result.bookings[0].reason — see BOOKING_REASON_CODES in
# virtuagym.v3.models. NOTE: a member without the required credit type is
# booked UNPAID rather than rejected — check payment_info if payment matters.
client.update_booking(events[0].event_id, {"member_id": 42, "presence": True})
client.cancel_booking(events[0].event_id, member_id=42, refund=False)
```

Note: occurrences of a recurring event **share the same `event_id`** and differ only in `datetime_start` — use `event_id` + `datetime_start` as the occurrence key.

## Async

Both clients have async twins with identical surfaces:

```python
from virtuagym import AsyncVirtuaGymClientV1

client = AsyncVirtuaGymClientV1(api_key="...", club_secret="...", club_id=12345)

async for page in client.members():
    ...
members = await client.all_members()
```

## Error handling

```python
from virtuagym import VirtuaGymApiError, VirtuaGymV3ApiError

try:
    client.member(999)
except VirtuaGymApiError as e:
    # v1: in-band API errors (reported with HTTP 200), real-HTTP-status
    # errors, and envelope failures.
    print(e.statuscode, e.statusmessage)  # e.g. 420 'Not found.'
```

- **`VirtuaGymApiError`** (v1) — `statuscode`, `statusmessage`, optional `errors` payload.
- **`VirtuaGymV3ApiError`** (v3) — real HTTP status in `http_status`, invalid field names in `fields`. On a 401 the client refreshes the token and retries once before raising.
- **`pydantic.ValidationError`** — the response did not match the documented schema, naming the exact offending field.

## Development

```bash
pip install -e .[dev]
pytest               # unit tests (offline, mocked HTTP)
ruff check . && ruff format --check . && mypy

# Smoke tests against the live API (read-only):
cp .env.example .env  # then fill in your credentials
pytest -m smoke
```

## License

[MIT](LICENSE)
