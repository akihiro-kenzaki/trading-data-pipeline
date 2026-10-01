import pytest
from ingest.common import normalize_order_ref, resolve_or_create_symbol


@pytest.mark.parametrize(
    "order_ref",
    ["348", "#348", "0348"],
)
def test_normalize_order_ref_valid_string(order_ref):
    result = normalize_order_ref(order_ref)
    assert result == 348


def test_normalize_order_ref_when_none_raises_value_error():
    with pytest.raises(ValueError):
        normalize_order_ref(None)


class FakeCursor:
    def __init__(self):
        self.calls = []

    def fetchone(self):
        return (42,)

    def execute(self, sql, params):
        self.calls.append((sql, params))


def test_resolve_or_create_symbol_has_symbol_in_database(monkeypatch):
    cur = FakeCursor()
    monkeypatch.setattr(cur, "fetchone", lambda: (99,))
    result = resolve_or_create_symbol(cur, "7203", "トヨタ")
    assert result == (99, False)
    assert len(cur.calls) == 1
    assert (cur.calls[0][0].startswith("SELECT")) == True
    assert (cur.calls[0][1]) == ("7203",)
