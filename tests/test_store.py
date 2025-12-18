import tempfile
import os
from store import init_db, save_trade, get_trades_for_mint
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
