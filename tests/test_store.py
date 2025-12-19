import tempfile
import os
from store import init_db, save_trade, get_trades_for_mint, compute_volumes_sql
from parse import Trade


def test_save_and_query(tmp_path):
    db_path = tmp_path / "test.db"
    conn = init_db(str(db_path))

    t = Trade(signature="S1", ts=1_700_000_000, mint="MINTX", token_delta=5.0, quote_mint="Q", quote_delta=-10.0, price=2.0)
    ok = save_trade(conn, t)
    assert ok is True

    rows = get_trades_for_mint(conn, "MINTX")
    assert len(rows) == 1
    assert rows[0].signature == "S1"

    # Duplicate insert should return False
    ok2 = save_trade(conn, t)
    assert ok2 is False

    conn.close()


def test_compute_volumes_sql(tmp_path):
    db_path = tmp_path / "agg.db"
    conn = init_db(str(db_path))

    now = 1_700_000_000
    t1 = Trade(signature="S1", ts=now - 30, mint="MINTX", token_delta=2.0)
    t2 = Trade(signature="S2", ts=now - 120, mint="MINTX", token_delta=-3.0)
    t3 = Trade(signature="S3", ts=now - 2000, mint="MINTX", token_delta=1.5)
    assert save_trade(conn, t1)
    assert save_trade(conn, t2)
    assert save_trade(conn, t3)

    vols = compute_volumes_sql(conn, "MINTX", now_ts=now)
    # 1m window should include t1 only (abs 2.0)
    assert vols["1m"] == 2.0
    # 5m window includes t1 and t2 -> 2 + 3 = 5
    assert vols["5m"] == 5.0
    # 15m includes t1,t2,t3? t3 at now-2000 (33m) -> excluded
    assert vols["15m"] == 5.0
    conn.close()
