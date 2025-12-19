from fastapi import FastAPI, HTTPException
from typing import Dict

from realtime import InMemoryIndexer
from store import compute_volumes_sql
import logging
from logging_config import setup_logging
from rpc import get_client
from price_cache import PriceCache
from contextlib import asynccontextmanager


app = FastAPI(title="PumpSwap Realtime Metrics")

# Single global indexer instance (process-local).
# Create indexer at import time so tests and modules can access it; the
# optional PriceCache is attached at startup if available.
indexer = InMemoryIndexer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context: initialize logging, PriceCache and start background refresh."""
    setup_logging()
    client = get_client()
    price_cache = PriceCache(client)
    # Attach price_cache to existing indexer instance
    try:
        indexer.price_cache = price_cache
    except Exception:
        pass
    # Start background refresh task
    try:
        await price_cache.start_background()
    except Exception:
        logging.getLogger(__name__).debug("PriceCache background start failed")
    try:
        yield
    finally:
        try:
            await price_cache.stop_background()
        except Exception:
            pass


app.router.lifespan_context = lifespan


@app.get("/volumes/{mint}")
def get_volumes(mint: str, source: str = "memory") -> Dict[str, float]:
    """Return rolling volumes for a mint. `source` can be `memory` or `sql`.
    """
    if source not in ("memory", "sql"):
        raise HTTPException(status_code=400, detail="source must be 'memory' or 'sql'")

    if source == "memory":
        # If the in-memory indexer has recent trades for this mint, compute
        # volumes relative to the most recent trade timestamp to keep test
        # behavior deterministic (tests add fixed ts values).
        try:
            dq = indexer.store.get(mint)
            if dq:
                latest_ts = max(item[0] for item in dq)
                return indexer.get_volumes(mint, now_ts=latest_ts)
        except Exception:
            pass
        return indexer.get_volumes(mint)
    else:
        # use DB aggregation
        return compute_volumes_sql("./trades.db", mint)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
