# metrics.py
from typing import Iterable, Dict, Optional
import time
from parse import Trade
from config import STABLECOIN_MINTS

WINDOWS = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
}

def compute_volumes(
    trades: Iterable[Trade],
    now: Optional[int] = None,
    return_usd: bool = False,
) -> Dict[str, float] | Dict[str, Dict[str, float]]:
    """
    Compute rolling volumes for each window.
    Returns mapping: {window: {"token": float, "usd": float}}
    """
    now = now or int(time.time())
    vols_token: Dict[str, float] = {k: 0.0 for k in WINDOWS}
    vols_usd: Dict[str, Dict[str, float]] = {k: {"token": 0.0, "usd": 0.0} for k in WINDOWS}
    for t in trades:
        age = now - t.ts
        if age < 0:
            # future block time?? just skip
            continue
        for label, secs in WINDOWS.items():
            if age <= secs:
                token_amt = abs(t.token_delta)
                vols_token[label] += token_amt
                # If trade price available and quote is a stablecoin, treat price as USD
                if t.price is not None and t.quote_mint in STABLECOIN_MINTS:
                    try:
                        vols_usd[label]["token"] += token_amt
                        vols_usd[label]["usd"] += token_amt * abs(t.price)
                    except Exception:
                        continue
    return vols_usd if return_usd else vols_token


def compute_age_seconds(
    trades: Iterable[Trade],
    now: Optional[int] = None,
) -> Optional[int]:
    now = now or int(time.time())
    ts_list = [t.ts for t in trades]
    if not ts_list:
        return None
    first_ts = min(ts_list)
    return now - first_ts
