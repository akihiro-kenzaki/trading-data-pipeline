import pytest
from ingest.common import normalize_order_ref


@pytest.mark.parametrize(
    "order_ref",
    ["348", "#348", "0348"],
)
def test_normalize_order_ref_valid_string(order_ref):
    result = normalize_order_ref(order_ref)
    assert result == 348


def test_normalize_order_when_none_raises_value_error():
    with pytest.raises(ValueError):
        normalize_order_ref(None)
