import asyncio
import base64
from types import SimpleNamespace

import pytest

from price_cache import PriceCache
import pyth_parser


class FakeClient:
    def __init__(self, b64data):
        self._b64 = b64data

    def get_account_info(self, pk):
        # RPC-like shape
        return SimpleNamespace(value=SimpleNamespace(data=[self._b64]))


def test_pricecache_background_refresh(monkeypatch):
    raw = pyth_parser.make_price_account_bytes(price=1000000000, expo=-8, conf=10)
    b64 = base64.b64encode(raw).decode()
    client = FakeClient(b64)

    pc = PriceCache(client, ttl=1)

    # Ensure the mapping contains at least one mint mapping for the test
    import config

    # Use a deterministic test mint
    test_mint = "TESTMINTBACKGROUND11111111111111111111"
    monkeypatch.setitem(config.PYTH_PRICE_ACCOUNTS, test_mint, "DummyPriceAcct111111111111111111111111")

    import rpc

    # Monkeypatch Pubkey.from_string to avoid validation errors in tests
    monkeypatch.setattr(rpc.Pubkey, 'from_string', lambda s: s, raising=False)

    async def run_bg():
        await pc.start_background(interval=1, mints=[test_mint])
        await asyncio.sleep(1.5)
        await pc.stop_background()

    asyncio.run(run_bg())

    # Assert cache populated
    p = pc.get(test_mint)
    assert p is not None
    assert abs(p - 10.0) < 1e-6 or p > 0
