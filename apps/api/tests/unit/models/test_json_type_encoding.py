"""The JSON column type encodes once on PostgreSQL and reads every stored shape.

Before 2026-11-16 the type `json.dumps`-ed every value and the PostgreSQL JSONB driver encoded it again, so ORM
writes landed as JSON strings that SQL-level JSON queries never matched. The read side must still accept those
legacy strings (until scripts/normalize_jsonb_strings.py unwraps them); a Python str value round-trips as before.
"""

import pytest
from sqlalchemy.dialects import postgresql, sqlite

from app.models.types import JSON

PG = postgresql.dialect()
SQLITE = sqlite.dialect()


def test_postgres_binds_the_value_as_is_so_the_driver_encodes_it_once():
    t = JSON()
    assert t.process_bind_param({"dhanam": "pro"}, PG) == {"dhanam": "pro"}
    assert t.process_bind_param(["a", "b"], PG) == ["a", "b"]
    assert t.process_bind_param(None, PG) is None


def test_a_str_value_round_trips_exactly_as_before():
    t = JSON()
    stored = t.process_bind_param("authorization_code,client_credentials", PG)
    assert stored == '"authorization_code,client_credentials"'
    assert t.process_result_value(stored, PG) == "authorization_code,client_credentials"


def test_sqlite_still_stores_text():
    assert JSON().process_bind_param({"a": 1}, SQLITE) == '{"a": 1}'


def test_reads_objects_and_legacy_strings_and_refuses_what_is_not_json():
    t = JSON()
    assert t.process_result_value({"a": 1}, PG) == {"a": 1}
    assert t.process_result_value('{"a": 1}', PG) == {"a": 1}  # a legacy double-encoded row
    assert t.process_result_value('["pwd"]', PG) == ["pwd"]
    assert t.process_result_value('{"a": 1}', SQLITE) == {"a": 1}
    assert t.process_result_value(None, PG) is None
    # Unchanged from before the fix: text that is not JSON is refused, never handed on as a str that code would
    # iterate character by character (scripts/audit_client_credentials_tier_claims.py relies on this).
    with pytest.raises(ValueError):
        t.process_result_value("authorization_code,client_credentials", PG)
