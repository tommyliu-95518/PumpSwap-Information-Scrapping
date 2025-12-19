from collections import deque, defaultdict
from typing import Dict, Deque, Tuple, Optional
from parse import Trade
import time

WINDOWS = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
}


class InMemoryIndexer:
    """Maintain in-memory rolling windows of absolute token volumes per mint.

    Usage:
      idx = InMemoryIndexer()
      idx.add_trade(trade)
      idx.get_volumes(mint)
    """

    def __init__(self, price_cache=None):
        # For each mint, keep deque of (ts, token_delta, quote_mint, price)
        self.store: Dict[str, Deque[Tuple[int, float, Optional[str], Optional[float]]]] = defaultdict(deque)
        # Optional PriceCache instance used for USD computations when trades are
        # not quoted in stablecoins.
        self.price_cache = price_cache

    def _prune(self, mint: str, now_ts: Optional[int] = None) -> None:
        now = int(now_ts or time.time())
        dq = self.store.get(mint)
        if not dq:
            return
        max_window = max(WINDOWS.values())
        cutoff = now - max_window
        # Pop left while oldest < cutoff
        while dq and dq[0][0] < cutoff:
            dq.popleft()

    def add_trade(self, trade: Trade) -> None:
        """Add a parsed trade to the in-memory indexer."""
        if not trade or not trade.mint:
            return
        dq = self.store[trade.mint]
        dq.append((int(trade.ts), float(trade.token_delta), trade.quote_mint, trade.price))
        # Keep deque size bounded by pruning old entries
        self._prune(trade.mint, trade.ts)

    def get_volumes(self, mint: str, now_ts: Optional[int] = None, return_usd: bool = False) -> Dict[str, float] | Dict[str, Dict[str, float]]:
        """Return rolling volumes for the given `mint`.

        By default returns mapping {window: token_sum}. If `return_usd=True` returns
        {window: {"token": float, "usd": float}}.
        """
        now = int(now_ts or time.time())
        self._prune(mint, now)
        dq = self.store.get(mint, deque())
        res_token: Dict[str, float] = {k: 0.0 for k in WINDOWS}
        res_usd: Dict[str, Dict[str, float]] = {k: {"token": 0.0, "usd": 0.0} for k in WINDOWS}
        from metrics import STABLECOIN_MINTS

        for ts, delta, quote_mint, price in dq:
            age = now - ts
            if age < 0:
                continue
            token_amt = abs(delta)
            for label, secs in WINDOWS.items():
                if age <= secs:
                    res_token[label] += token_amt
                    # USD computation order of preference:
                    # 1) trade has price and quote is stablecoin -> use it
                    # 2) otherwise, use price_cache if available for this mint
                    usd_added = 0.0
                    if price is not None and quote_mint in STABLECOIN_MINTS:
                        try:
                            usd_val = token_amt * abs(price)
                            res_usd[label]["token"] += token_amt
                            res_usd[label]["usd"] += usd_val
                            usd_added = usd_val
                        except Exception:
                            pass
                    if usd_added == 0.0 and self.price_cache is not None:
                        try:
                            p = self.price_cache.get(mint)
                            if p is not None:
                                usd_val = token_amt * abs(p)
                                res_usd[label]["token"] += token_amt
                                res_usd[label]["usd"] += usd_val
                        except Exception:
                            pass

        return res_usd if return_usd else res_token
