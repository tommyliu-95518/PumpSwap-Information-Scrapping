import time

from price_cache import PriceCache


class FakeClient:
    pass


def test_pricecache_get_and_set(monkeypatch):
    client = FakeClient()
    pc = PriceCache(client, ttl=5)

    # Patch the module-level get_price_for_mint that PriceCache imports
    import price_cache as pc_mod

    def fake_get_price_for_mint(client_arg, mint):
        assert client_arg is client
        return 12.34

    monkeypatch.setattr(pc_mod, 'get_price_for_mint', fake_get_price_for_mint)

    # Initially cache is empty -> should fetch via patched function
    p = pc.get('SOME_MINT')
    assert p == 12.34

    # Now set a different price and ensure get returns cached value until TTL expires
    pc.set('SOME_MINT', 56.78)
    p2 = pc.get('SOME_MINT')
    assert p2 == 56.78

    # Expire cache and ensure fetch happens again
    # manipulate internal timestamp to simulate expiry
    old_price, old_ts = pc._cache['SOME_MINT']
    pc._cache['SOME_MINT'] = (old_price, time.time() - 10)

    p3 = pc.get('SOME_MINT')
    assert p3 == 12.34
