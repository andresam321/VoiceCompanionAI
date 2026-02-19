# tests/conftest.py
from __future__ import annotations

import uuid
import pytest


@pytest.fixture
def sample_traits() -> dict:
    return {
        "warmth": 0.9,
        "humor": 0.7,
        "curiosity": 0.8,
        "energy": 0.6,
        "verbosity": 0.4,
    }


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.uuid4()
