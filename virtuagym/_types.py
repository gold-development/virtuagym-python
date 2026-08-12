"""Shared type helpers for the wire format's loose typing."""

from typing import Annotated, Any

from pydantic import BeforeValidator


def _to_str(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return str(value)
    return value


# The API returns some ids as int in one place and string in another (see
# API-FINDINGS in gold-development/virtuagym-node); coerce to string for a
# stable type.
CoercedStr = Annotated[str, BeforeValidator(_to_str)]
