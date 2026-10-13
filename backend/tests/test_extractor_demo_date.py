import sys
from types import SimpleNamespace

from datetime import datetime

from app.ai.extractor import (
    _extract_appointment_demo,
    extract_appointment,
    normalize_date,
)


def test_extract_appointment_demo_day_first_ordinal_date():
    extracted = _extract_appointment_demo("I want appointment on 15th September", {})
    assert extracted["date"] == datetime(2026, 9, 15).date().isoformat()


def test_normalize_date_supports_ordinal_month_names():
    assert normalize_date("15th September") == datetime(2026, 9, 15).date().isoformat()


def test_extract_appointment_demo_supports_abbreviated_day_first_month():
    extracted = _extract_appointment_demo("10 nov", {"date": None, "time": None})

    assert extracted["date"] == normalize_date("10 nov")
    assert "time" not in extracted


def test_extract_appointment_demo_does_not_treat_bare_day_as_time_before_date():
    extracted = _extract_appointment_demo("10", {"date": None, "time": None})

    assert "date" not in extracted
    assert "time" not in extracted


def test_extract_appointment_uses_local_date_when_ai_omits_it(monkeypatch):
    class FakeGroq:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content="{}")
                            )
                        ]
                    )
                )
            )

    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=FakeGroq))

    extracted = extract_appointment("10 nov", {"date": None, "time": None})

    assert extracted["date"] == normalize_date("10 nov")
