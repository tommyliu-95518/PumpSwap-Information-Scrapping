from realtime import InMemoryIndexer
from parse import Trade


def test_realtime_windows_simple():
    idx = InMemoryIndexer()
    now = 1_700_000_000
    t1 = Trade(signature="A", ts=now - 30, mint="MINT1", token_delta=2.0)
    t2 = Trade(signature="B", ts=now - 120, mint="MINT1", token_delta=-3.0)
    t3 = Trade(signature="C", ts=now - 2000, mint="MINT1", token_delta=1.5)

    idx.add_trade(t1)
    idx.add_trade(t2)
    idx.add_trade(t3)

    vols = idx.get_volumes("MINT1", now_ts=now)
    assert vols["1m"] == 2.0
    assert vols["5m"] == 5.0
    assert vols["15m"] == 5.0
