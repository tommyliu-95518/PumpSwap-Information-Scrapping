import base64
from types import SimpleNamespace

import pytest

import pyth_parser
import rpc


def test_parse_roundtrip():
    raw_bytes = pyth_parser.make_price_account_bytes(price=123456789, expo=-6, conf=1000, status=1, valid_slot=10, publish_slot=20)
    parsed = pyth_parser.parse_price_account(raw_bytes)
    assert parsed is not None
    assert parsed['price'] == 123456789
    assert parsed['expo'] == -6
    assert parsed['conf'] == 1000
    # computed float price
    computed = float(parsed['price']) * (10 ** parsed['expo'])
    assert abs(computed - 123.456789) < 1e-9


def test_rpc_integration_with_local_parser():
    # Build a pyth-like account and encode in base64 as RPC returns
    raw_bytes = pyth_parser.make_price_account_bytes(price=2500000000, expo=-8, conf=5000)
    b64 = base64.b64encode(raw_bytes).decode()

    class FakeClient:
        def get_account_info(self, pk):
            return SimpleNamespace(value=SimpleNamespace(data=[b64]))

    client = FakeClient()
    # Temporarily monkeypatch Pubkey.from_string so the fake client receives our dummy
    orig_from_string = rpc.Pubkey.from_string
    try:
        rpc.Pubkey.from_string = lambda s: s
        price = rpc.get_price_from_pyth(client, "DummyPriceAccount111111111111111111111111")
    finally:
        rpc.Pubkey.from_string = orig_from_string

    assert price is not None
    # expected price = 2500000000 * 1e-8 = 25.0
    assert abs(price - 25.0) < 1e-9
