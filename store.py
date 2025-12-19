import sqlite3
from typing import Optional, List, Dict
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


# Rolling windows (seconds) used by metrics
WINDOWS = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
}


def compute_volumes_sql(conn_or_path, mint: str, now_ts: Optional[int] = None, return_usd: bool = False, client=None) -> Dict[str, float] | Dict[str, Dict[str, float]]:
    """Compute rolling volumes for `mint` using SQL aggregation on stored trades.

    Returns dict mapping window label to sum(abs(token_delta)).
    """
    close_conn = False
    if isinstance(conn_or_path, str):
        conn = init_db(conn_or_path)
        close_conn = True
    else:
        conn = conn_or_path

    now = int(now_ts or __import__("time").time())
    res = {}
    cur = conn.cursor()
    # Return token + USD volumes per window. Use stored `price` and `quote_mint`
    from metrics import STABLECOIN_MINTS

    # If a client is provided, attempt to fetch a Pyth price for the mint
    pyth_price = None
    try:
        if client is not None:
            from rpc import get_price_for_mint

            pyth_price = get_price_for_mint(client, mint)
            if pyth_price is not None:
                try:
                    pyth_price = float(pyth_price)
                except Exception:
                    pyth_price = None
    except Exception:
        pyth_price = None

    for label, secs in WINDOWS.items():
        since = now - secs
        rows = cur.execute(
            "SELECT token_delta, price, quote_mint FROM trades WHERE mint = ? AND ts >= ?",
            (mint, since),
        ).fetchall()
        token_total = 0.0
        usd_total = 0.0
        for (td, price, quote_mint) in rows:
            try:
                token_amt = abs(float(td))
            except Exception:
                continue
            token_total += token_amt
            if price is not None and quote_mint in STABLECOIN_MINTS:
                try:
                    usd_total += token_amt * abs(float(price))
                except Exception:
                    pass
        if return_usd:
            res[label] = {"token": token_total, "usd": usd_total}
        else:
            res[label] = token_total

    if close_conn:
        conn.close()
    return res
