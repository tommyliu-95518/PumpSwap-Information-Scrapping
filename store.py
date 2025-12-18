import sqlite3
from typing import Optional, List
from parse import Trade
import json


def init_db(path: str) -> sqlite3.Connection:
    """Initialize SQLite DB and return a connection."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            signature TEXT PRIMARY KEY,
            ts INTEGER,
            mint TEXT,
            token_delta REAL,
            quote_mint TEXT,
            quote_delta REAL,
            price REAL,
            raw TEXT
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mint_ts ON trades(mint, ts)")
    conn.commit()
    return conn


def save_trade(conn_or_path, trade: Trade) -> bool:
    """Save a `Trade` to the DB.

    Returns True if inserted, False if it was a duplicate (signature exists).
    """
    close_conn = False
    if isinstance(conn_or_path, str):
        conn = init_db(conn_or_path)
        close_conn = True
    else:
        conn = conn_or_path

    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO trades(signature, ts, mint, token_delta, quote_mint, quote_delta, price, raw) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trade.signature,
                trade.ts,
                trade.mint,
                trade.token_delta,
                trade.quote_mint,
                trade.quote_delta,
                trade.price,
                json.dumps(trade.__dict__),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # signature primary key conflict -> already present
        return False
    finally:
        if close_conn:
            conn.close()


def _row_to_trade(row) -> Trade:
    signature, ts, mint, token_delta, quote_mint, quote_delta, price, raw = row
    # Attempt to use raw JSON if present to preserve types, fall back to constructor
    try:
        data = json.loads(raw) if raw else {}
        return Trade(
            signature=signature,
            ts=int(ts),
            mint=mint,
            token_delta=float(token_delta),
            quote_mint=data.get("quote_mint") if data else quote_mint,
            quote_delta=data.get("quote_delta") if data else quote_delta,
            price=data.get("price") if data else price,
        )
    except Exception:
        return Trade(
            signature=signature,
            ts=int(ts),
            mint=mint,
            token_delta=float(token_delta),
            quote_mint=quote_mint,
            quote_delta=quote_delta,
            price=price,
        )


def get_trades_for_mint(conn_or_path, mint: str, since_ts: Optional[int] = None) -> List[Trade]:
    close_conn = False
    if isinstance(conn_or_path, str):
        conn = init_db(conn_or_path)
        close_conn = True
    else:
        conn = conn_or_path

    cur = conn.cursor()
    if since_ts is None:
        rows = cur.execute(
            "SELECT signature, ts, mint, token_delta, quote_mint, quote_delta, price, raw FROM trades WHERE mint = ? ORDER BY ts ASC",
            (mint,),
        ).fetchall()
    else:
        rows = cur.execute(
            "SELECT signature, ts, mint, token_delta, quote_mint, quote_delta, price, raw FROM trades WHERE mint = ? AND ts >= ? ORDER BY ts ASC",
            (mint, since_ts),
        ).fetchall()

    trades = [_row_to_trade(r) for r in rows]
    if close_conn:
        conn.close()
    return trades
