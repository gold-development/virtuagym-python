"""Typed models for the Virtuagym v3 API.

Field names match the API's wire format. Quirks noted below were verified
against the live API — see API-FINDINGS.md in gold-development/virtuagym-node.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from virtuagym._types import CoercedStr

#: Documented lead statuses.
LEAD_STATUSES = {
    1: "New",
    2: "Contacted",
    3: "In Contact",
    4: "Appointment made",
    5: "Appointment held",
    6: "Free Trial",
    7: "Sign up scheduled",
    8: "No show",
    9: "Closed refused",
    10: "Closed lost contact",
    11: "Closed disqualified",
    12: "Closed won",
    13: "Closed - third party aggregators",
}

#: Reason codes reported per booking attempt by the schedule API.
BOOKING_REASON_CODES = {
    1: "ok",
    2: "participant_added",
    101: "not_available",
    102: "participant_already_there",
    103: "full_book",
    105: "not_credits",
    108: "outside_min_time_between_bookings",
    114: "too_early_to_book",
    115: "booking_disabled",
    116: "booking_disabled_reached_no_show_limit",
}


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class Lead(_Model):
    """A lead as returned by the v3 leads API.

    NOTE: the live API serializes every field as a string — ids, flags
    ("0"/"1") and timestamps (SECONDS since epoch) included. Empty values
    are empty strings, except birthday which can be null.
    """

    lead_id: str
    lead_guid: str
    club_id: str
    #: See LEAD_STATUSES for the documented values.
    status_id: str
    source_id: str
    #: Member id of the staff member who owns the lead; "0" when unset.
    owner_id: str
    firstname: str
    lastname: str
    email: str
    phone: str
    mobile: str
    #: "f" = female, "m" = male; empty when unset.
    gender: str
    #: YYYY-MM-DD, or None when unset.
    birthday: str | None
    address: str
    address_2: str
    zip_code: str
    city: str
    state: str
    country: str
    language: str
    picture: str
    #: Member id once the lead converted; "0" otherwise.
    converted_to_member_id: str
    external_id: str
    lead_since: str | None
    created_by_user_id: str
    edited_by_user_id: str
    #: "0" or "1".
    deleted: str
    #: Timestamp in SECONDS, as a string.
    timestamp_created: str
    timestamp_edited: str
    #: "0" or "1".
    inactive: str


class LeadOwner(_Model):
    """Undocumented: the leads list response includes an owners map
    (owner_id → staff member) alongside the leads."""

    member_id: str
    firstname: str
    lastname: str


class SchedulePaymentInfo(_Model):
    """Payment info of a participant's booking.

    The datetime_* fields are undocumented and, uniquely for this API,
    RFC-1123 date strings ("Wed, 27 Mar 2024 17:10:08 GMT") rather than
    timestamps.
    """

    paid_status: bool | None = None
    amount: float | None = None
    credit_type: str | None = None
    datetime_paid: str | None = None
    datetime_update: str | None = None
    datetime_created: str | None = None


class ScheduleParticipant(_Model):
    """A member booked into a schedule event.

    The events and bookings endpoints encode absent values differently
    (null vs 0 vs "") — see API-FINDINGS item 53.
    """

    member_id: int
    #: The member's id in the super club (superclub setups only).
    original_member_id: int | None = None
    name: str | None = None
    phone_number: str | None = None
    email: str | None = None
    photo: str | None = None
    presence: bool | None = None
    deleted: bool | None = None
    payment_info: SchedulePaymentInfo | None = None


class ScheduleGuest(_Model):
    """A guest (non-member) booked into a schedule event."""

    #: Integer in the events spec, string in the bookings spec; coerced.
    external_id: CoercedStr | None = None
    email: str | None = None
    name: str | None = None
    phone_number: str | None = None
    presence: bool | None = None
    follow_up_as_lead: bool | None = None
    deleted: bool | None = None


class ScheduleActivitySettings(_Model):
    """Booking-rule ranges configured on the activity (ms; -1 = disabled)."""

    bookable_till_range: dict[str, int | None] | None = None
    booking_closes_range: int | None = None
    free_cancellation_range: int | None = None
    cancellation_range: int | None = None
    min_time_between_bookings_range: int | None = None
    reschedule_range: int | None = None


class ScheduleActivityCategory(_Model):
    category_guid: str
    category_name: str | None = None
    #: Locale → translated fields, e.g. {"en": {"category_name": …}}.
    trans: dict[str, Any] | None = None
    category_type: int | None = None
    #: 0-3; how the instructor name is displayed.
    instructor_name_display: int | None = None
    capacity_display: int | None = None


class ScheduleEventCost(_Model):
    """Credit cost of booking the activity."""

    credit_guid: str | None = None
    credit_name: str | None = None
    credit_amount: int | None = None
    credit_priority: int | None = None


class ScheduleActivity(_Model):
    activity_id: int
    activity_name: str | None = None
    activity_description: str | None = None
    trans: dict[str, Any] | None = None
    image: str | None = None
    visibility: int | None = None
    settings: ScheduleActivitySettings | None = None
    category: ScheduleActivityCategory | None = None
    costs: list[ScheduleEventCost] | None = None
    tryout_enabled: bool | None = None


class ScheduleStaff(_Model):
    staff_guid: str | None = None
    staff_member_id: int | None = None
    staff_name: str | None = None
    staff_image: str | None = None


class ScheduleLocation(_Model):
    location_id: str | None = None
    location_name: str | None = None
    trans: dict[str, Any] | None = None


class ScheduleEvent(_Model):
    """An event on the club's appointment schedule (v3).

    The bookings list endpoint returns the same shape with only the
    booking-related fields populated.
    """

    #: NOT unique per row (verified live): occurrences of a recurring event
    #: share the event_id and differ only in datetime_start/datetime_end.
    event_id: str
    #: UTC milliseconds.
    datetime_start: int
    datetime_end: int
    created_timestamp: int | None = None
    updated_timestamp: int | None = None
    meeting_link: str | None = None
    spots_left: int | None = None
    capacity: int | None = None
    track_participants_presence: int | None = None
    participants_presence_confirmed: bool | None = None
    deleted: bool | None = None
    title: str | None = None
    activity: ScheduleActivity | None = None
    location: ScheduleLocation | None = None
    staff: ScheduleStaff | None = None
    participants: list[ScheduleParticipant] | None = None
    guests: list[ScheduleGuest] | None = None


class BookingAttempt(_Model):
    """One booking attempt in the response of creating a booking.

    day/time_start/time_end are CLUB-LOCAL (verified live: an 11:00 UTC
    event books as "13:00:00" for a Europe/Amsterdam club), unlike the UTC
    millisecond datetimes used everywhere else in the schedule API.
    """

    booked: bool
    #: YYYY-MM-DD, club-local.
    day: str | None = None
    #: See BOOKING_REASON_CODES.
    reason: int | None = None
    #: HH:MM:SS, club-local.
    time_start: str | None = None
    time_end: str | None = None
    #: Timestamp (ms) when a booking block expires; only when blocked.
    booking_blocked_until: int | None = None


class BookingCreated(_Model):
    """Response of creating a booking on a schedule event."""

    bookings: list[BookingAttempt] = []
    total_bookings: int | None = None
