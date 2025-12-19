from typing import Optional, Dict, Tuple
import time
import logging

from config import PYTH_PRICE_ACCOUNTS
from rpc import get_price_for_mint

logger = logging.getLogger(__name__)


class PriceCache:
    """Simple on-demand Pyth price cache.

    Usage:
      cache = PriceCache(client, ttl=30)
      price = cache.get(mint)

    The cache will attempt to fetch prices from Pyth via `get_price_for_mint()`
    when a value is missing or older than `ttl` seconds.
    """

    def __init__(self, client, ttl: int = 30):
        self.client = client
        self.ttl = ttl
        self._cache: Dict[str, Tuple[float, float]] = {}  # mint -> (price, ts)
        self._task = None
        self._stopping = False

    async def _refresh_loop(self, interval: Optional[int] = None, mints: Optional[list] = None):
        """Background task that refreshes configured mints periodically."""
        if interval is None:
            interval = int(self.ttl)
        while not self._stopping:
            try:
                keys = mints if mints is not None else list(PYTH_PRICE_ACCOUNTS.keys())
                for mint in keys:
                    try:
                        p = get_price_for_mint(self.client, mint)
                        if p is not None:
                            self.set(mint, float(p))
                    except Exception:
                        logger.debug("Failed to refresh price for %s", mint)
            except Exception:
                logger.exception("Error during price cache refresh loop")
            await __import__("asyncio").sleep(interval)

    async def start_background(self, interval: Optional[int] = None, mints: Optional[list] = None):
        """Start background refresh task. Safe to call multiple times.

        `mints` defaults to the keys present in `PYTH_PRICE_ACCOUNTS`.
        """
        if self._task is not None and not self._task.done():
            return
        self._stopping = False
        loop = __import__("asyncio").get_event_loop()
        self._task = loop.create_task(self._refresh_loop(interval=interval, mints=mints))

    async def stop_background(self):
        """Stop background task and wait for it to finish."""
        self._stopping = True
        if self._task is not None:
            try:
                await self._task
            except Exception:
                pass
            self._task = None

    def get(self, mint: str) -> Optional[float]:
        now = time.time()
        rec = self._cache.get(mint)
        if rec:
            price, ts = rec
            if now - ts <= self.ttl:
                return price

        # Attempt to fetch from Pyth mapping or other RPC helper
        try:
            p = get_price_for_mint(self.client, mint)
            if p is not None:
                price = float(p)
                self._cache[mint] = (price, now)
                return price
        except Exception as e:
            logger.debug("PriceCache get failed for %s: %s", mint, e)

        return None

    def set(self, mint: str, price: float) -> None:
        self._cache[mint] = (float(price), time.time())
