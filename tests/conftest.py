import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing environment variable {name} — add it to your .env file")
    return value


@pytest.fixture()
def club_id() -> int:
    return int(require_env("VIRTUAGYM_CLUB_ID"))
