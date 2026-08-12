"""Typed models for the Virtuagym v1 API.

Field names match the API's wire format (snake_case), including the API's
own spelling of ``priviliges``. Quirks noted below were verified against the
live API — see API-FINDINGS.md in gold-development/virtuagym-node.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from virtuagym._types import CoercedStr

#: Privileges supported by the employee endpoints. 'default' is added for
#: each employee.
EMPLOYEE_PRIVILEGES = (
    "club_manager",
    "assistent_manager",
    "marketing_manager",
    "coach",
    "financial",
    "employee",
    "scheduling",
    "default",
)

#: Documented note types; the error-message table omits "checkup" but it works.
NOTE_TYPES = ("general", "coaching", "products", "invoices", "files", "checkup")

#: The bodymetric types documented as assignable via the API.
BODYMETRIC_TYPES = (
    "weight", "height", "bmi", "fat", "waist", "number_crunches",
    "number_lunges", "number_pushups_knees", "number_pushups", "hr_exercise",
    "hr_rest", "visceral", "musclemass", "muscle_perc", "metabolicrate",
    "metabolicage", "bonemass", "bonemass_percent", "bodywater",
)  # fmt: skip


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class MembershipInstance(_Model):
    """A membership instance (contract) of a member.

    The membership-instance endpoint returns real booleans, but the
    member-embedded memberships array uses 0/1; both are normalized to bool.
    """

    instance_id: int
    member_id: int
    membership_id: int
    active: bool
    #: Manually cancelled by an employee with termination in the future.
    cancelled: bool
    #: Already renewed at this point (vs still in its initial period).
    contract_autorenewed: bool
    #: Reached the contract end date automatically and was not renewed.
    completed: bool
    #: Paused by an employee.
    paused: bool
    #: Manually cancelled by an employee with immediate termination.
    stopped: bool
    #: The actual start date of the membership (yyyy-mm-dd).
    start_date: str
    contract_start_date: str
    contract_end_date: str
    membership_name: str


class Member(_Model):
    """A club member."""

    member_id: int
    #: The club the member belongs to (a sub-club in case of a chain).
    club_id: int
    firstname: str
    lastname: str
    email: str
    active: bool
    is_pro: bool
    #: Timestamp (ms) in live responses, but the docs also show "YYYY-MM-DD".
    member_since: int | str
    #: Timestamp (ms) last changed; used as pagination cursor.
    timestamp_edit: int
    #: Custom ID from the external system ("Own member ID" in Virtuagym).
    club_member_id: str | None = None
    external_id: str | None = None
    #: Documented as "m"/"f", but "u" (unspecified) occurs in live data.
    gender: str | None = None
    birthday: str | None = None
    lang: str | None = None
    zip: str | None = None
    street: str | None = None
    street_extra: str | None = None
    place: str | None = None
    country: str | None = None
    formatted_address: str | None = None
    phone: str | None = None
    mobile: str | None = None
    rfid_tag: str | None = None
    early_booking_access: bool | None = None
    #: Only present when requested via the ``with`` option.
    memberships: list[MembershipInstance] | None = None
    #: Timestamp (ms) the member was registered. Undocumented.
    registration_date: int | None = None
    original_member_id: int | None = None
    #: ID of the linked user account. Undocumented; absent for some members.
    user_id: int | None = None
    business_guid: str | None = None


class Employee(_Model):
    """A club employee."""

    member_id: int
    club_id: int
    firstname: str
    lastname: str
    email: str
    active: bool
    is_pro: bool
    #: Timestamp (ms) the employee made an account.
    member_since: int
    #: Timestamp (ms) last changed; used as pagination cursor.
    timestamp_edit: int
    club_member_id: str | None = None
    external_id: str | None = None
    #: Documented as "m"/"f", but "u" (unspecified) occurs in live data.
    gender: str | None = None
    birthday: str | None = None
    lang: str | None = None
    zip: str | None = None
    street: str | None = None
    street_extra: str | None = None
    place: str | None = None
    country: str | None = None
    formatted_address: str | None = None
    phone: str | None = None
    mobile: str | None = None
    rfid_tag: str | None = None
    #: Comma-separated privileges, e.g. "default,club_manager". Spelling
    #: matches the wire format.
    priviliges: str | None = None
    registration_date: int | None = None
    original_member_id: int | None = None
    user_id: int | None = None
    early_booking_access: bool | None = None


class ActivateUserResult(_Model):
    member_id: int
    user_id: int
    club_id: int


class ClubEvent(_Model):
    """An event on the club's (legacy) schedule."""

    #: Declared int by the docs but returned as strings like
    #: "1945791969-54d4caf4db7821-10175268"; numbers coerced to strings.
    event_id: CoercedStr
    schedule_id: int
    #: Datetime ("YYYY-MM-DD HH:mm:ss") in the club timezone.
    start: str
    end: str
    title: str
    activity_id: int
    club_id: int
    employee_note: str | None = None
    #: The id of the instructor (0 when none).
    instructor_id: int | None = None
    attendees: int | None = None
    max_places: int | None = None
    #: Whether the event is bookable: 1 = true, 0 = false.
    bookable: Literal[0, 1] | None = None
    cancel_before_duration: int | None = None
    #: E.g. "1 months".
    booking_in_advance_duration: str | None = None
    canceled: bool | None = None
    language: str | None = None
    #: Participant info is only reliable when the instructor confirmed
    #: presence.
    presence_saved: bool | None = None


class EventParticipant(_Model):
    """A booking of a member (or guest) into a club event."""

    event_participant_id: int
    event_id: CoercedStr
    member_id: int
    timestamp_edit: int
    email_address: str | None = None
    #: The guest's name; only filled when fill_guestname is requested.
    user_name: str | None = None
    notes: str | None = None
    present: bool | None = None
    absence_reason: str | None = None
    has_paid: bool | None = None
    ticket_printed: bool | None = None


class EventParticipantCreated(_Model):
    """Response of a successful booking creation."""

    member_id: int
    event_id: CoercedStr
    event_participant_id: int
    message: str | None = None


class MembershipContract(_Model):
    """The contract returned when creating a membership instance."""

    id: int
    #: Documented as string but returned as number; coerced to string.
    contract_number: CoercedStr
    membership_id: int
    member_id: int
    start_date: str
    contract_start_date: str | None = None
    contract_end_date: str | None = None
    contract_active: bool | None = None
    contract_payment_method: str | None = None
    discount_id: int | None = None
    discount_name: str | None = None
    discount_amount: float | None = None
    #: Docs list "percentage"/"monetary", but their examples show "percent".
    discount_amount_type: str | None = None
    discount_start_date: str | None = None
    discount_duration: dict[str, int | str | None] | None = None


class MembershipClubTax(_Model):
    #: Returned as number or numeric string; coerced to number.
    tax_id: int
    tax_name: str | None = None
    tax_percentage: float | None = None


class MembershipAccessTime(_Model):
    #: Day of the week, e.g. "Monday".
    day: str
    #: HH:mm:ss.
    start_time: str
    end_time: str


class MembershipDefinition(_Model):
    """A membership definition (the product a club sells)."""

    membership_id: int
    membership_name: str
    membership_group: str | None = None
    membership_notes: str | None = None
    membership_availability_start: str | None = None
    membership_availability_end: str | None = None
    membership_available_online: bool | None = None
    membership_duration: int | None = None
    #: "weeks" or "months".
    membership_duration_type: str | None = None
    membership_auto_renew: bool | None = None
    membership_pro_rata_start: bool | None = None
    membership_renew_duration: int | None = None
    membership_renew_term: str | None = None
    membership_renew_before: int | None = None
    membership_renew_before_term: str | None = None
    membership_renew_price: float | None = None
    membership_price: float | None = None
    #: "total", "monthly", "weekly" or "four_weekly".
    membership_price_term: str | None = None
    membership_income_category: str | None = None
    membership_registration_fee: float | None = None
    membership_club_tax: MembershipClubTax | None = None
    membership_billing_cycle: str | None = None
    default_payment_method: str | None = None
    tmp_default_payment_method: str | None = None
    membership_creation_date: str | None = None
    membership_last_edit_date: str | None = None
    #: E.g. "10 days", "1 weeks".
    membership_invoice_creation_term: str | None = None
    access_times: list[MembershipAccessTime] | None = None


class ClubTax(_Model):
    #: The GUID of the club tax (the docs table wrongly declares an int).
    tax_id: CoercedStr
    tax_name: str
    #: The percentage as a decimal string, e.g. "21.00".
    tax_perc: str
    #: Undocumented numeric id; this is the id referenced by invoice rows
    #: (club_tax_id) and membership-instance creation (tax_id).
    club_tax_id: int | None = None
    date_from: str | None = None


class IncomeCategory(_Model):
    #: The GUID of the income category (an older docs revision shows numeric
    #: ids; numbers are coerced to strings).
    income_category_id: CoercedStr
    income_category_name: str
    #: Undocumented; returned by the live API.
    name_id: str | None = None
    default_tax: str | None = None
    default_tax_id: int | None = None


class InvoiceRow(_Model):
    """A row (child) of an invoice."""

    guid: str
    product_name: str
    product_count: int
    #: Price including VAT.
    price: float
    price_ex_vat: float
    vat: float
    currency: str
    deleted: bool
    #: The timestamp (date) of the invoice (seconds).
    timestamp: int
    timestamp_edit: int
    timestamp_created: int
    club_tax_id: int
    contract_id: int | None = None
    retail_product_id: int | None = None
    #: Undocumented.
    sales_user_id: int | None = None
    product_desc: str | None = None
    payment_method: str | None = None
    new_payment_method: str | None = None
    #: YYYY-MM-DD; shown in docs examples but absent from the field table.
    start_period: str | None = None
    end_period: str | None = None
    is_concept: bool | None = None
    income_category: str | None = None
    position: int | None = None
    #: E.g. "api_created".
    origin: str | None = None
    timestamp_paid: int | None = None
    club_tax_name: str | None = None
    club_tax_perc: float | None = None
    related_invoice: str | None = None


class Invoice(_Model):
    """A parent invoice with its rows."""

    guid: str
    club_id: int
    name: str
    price: float
    price_ex_vat: float
    currency: str
    paid: bool
    amount_due: float
    deleted: bool
    #: The timestamp (date) of the invoice (seconds).
    timestamp: int
    timestamp_edit: int
    timestamp_created: int
    rows: list[InvoiceRow]
    #: The id of the invoice (0 if the invoice is a concept).
    id: int | None = None
    contract_id: int | None = None
    retail_product_id: int | None = None
    member_id: int | None = None
    sales_user_id: int | None = None
    business_guid: str | None = None
    invoice_text_guid: str | None = None
    desc: str | None = None
    payment_method: str | None = None
    new_payment_method: str | None = None
    #: 0 open, 1 pending, 2 paid.
    paid_status: int | None = None
    is_offer: bool | None = None
    is_temporary: bool | None = None
    is_sent: bool | None = None
    is_concept: bool | None = None
    timestamp_paid: int | None = None
    timestamp_status: int | None = None
    extra_invoice_field_1: str | None = None
    extra_invoice_field_2: str | None = None
    extra_invoice_field_3: str | None = None
    employee_extra_field: str | None = None
    invoice_related_invoice: str | None = None
    free_invoice_text: str | None = None


class Visit(_Model):
    """A check-in/check-out visit of a member."""

    id: int
    club_id: int
    member_id: int
    #: Timestamp (ms) of the check-in.
    check_in_timestamp: int
    #: Timestamp (ms) of the check-out; 0 while the member is checked in.
    check_out_timestamp: int
    #: Documented values: "ok", "warning", "rejected".
    status: str
    status_message: str | None = None


class VisitRegistered(_Model):
    """Response of a successful check-in/check-out registration."""

    #: Check-in and check-out of one visit share the same id.
    id: int
    member_id: int
    message: str | None = None


class MemberNote(_Model):
    """A note on a club member's clients & staff page."""

    note_id: int
    member_id: int
    #: Timestamp created — in SECONDS, unlike most endpoints.
    timestamp: int
    note_text: str
    #: Documented values: general, coaching, products, invoices, files, checkup.
    note_type: str
    #: Undocumented; the user who wrote the note.
    from_user_id: int | None = None
    from_user_avatar: str | None = None
    from_user_name: str | None = None
    deleted: bool | None = None


class MemberNoteCreated(_Model):
    """Response of a successful note creation."""

    member_id: int
    note_id: int
    note: str | None = None


class MemberCredit(_Model):
    """The credits of one member in one service type.

    Rows have no unique id; identity is the (member_id, service_type) pair.
    """

    club_id: int
    member_id: int
    #: Normalized service type, e.g. "access", "solarium".
    service_type: str
    credit_amount: float
    credit_unlimited: bool
    #: Timestamp in SECONDS (the docs claim milliseconds).
    timestamp_created: int
    timestamp_edited: int
    #: Undocumented; present on a few rows. Timestamp in seconds.
    ts_needs_update: int | None = None


class CreditTransaction(_Model):
    """Response of a credit allocation."""

    member_id: int
    #: "Transaction completed", or "Already picked up or completed" when the
    #: same client_id was already processed (idempotent replay).
    message: str | None = None


class Bodymetric(_Model):
    """One bodymetric history entry of a member."""

    id: int
    #: Live data contains undocumented types (e.g. "sleep_score") beyond the
    #: documented BODYMETRIC_TYPES.
    type: str
    value: float
    #: Timestamp of the measurement, in seconds.
    timestamp: int
    #: Undocumented; the linked user account id (not the member_id).
    user_id: int | None = None
    unit: str | None = None
    #: 0/1 in the wire format; normalized to bool.
    deleted: bool | None = None
    #: Undocumented; timestamp (seconds) of the last edit.
    timestamp_edit: int | None = None


class BodymetricUpdated(_Model):
    """Response of a bodymetric update."""

    id: int
