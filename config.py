"""Configuration helpers: read from environment with sensible defaults."""
import os
import json
from typing import Set, Dict


def _parse_csv(s: str) -> Set[str]:
    return {p.strip() for p in s.split(",") if p.strip()}


# Default known stablecoin mint addresses (mainnet canonical):
# USDC: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
# USDT: Es9vMFrzaCERmJfr4S7f1KkGm8e7c9g2p2u7r2z1r5t (placeholder)
DEFAULT_STABLECOINS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "Es9vMFrzaCERmJfr4S7f1KkGm8e7c9g2p2u7r2z1r5t",
}


STABLECOIN_MINTS: Set[str] = DEFAULT_STABLECOINS.copy()
env_sc = os.getenv("STABLECOIN_MINTS")
if env_sc:
    try:
        STABLECOIN_MINTS = _parse_csv(env_sc)
    except Exception:
        STABLECOIN_MINTS = DEFAULT_STABLECOINS.copy()


# Optional mapping of token mint -> Pyth price account pubkey as JSON string
# Example: export PYTH_PRICE_ACCOUNTS='{"SOL": "<pyth_pubkey>", "So1111...": "<pyth_pubkey>"}'
PYTH_PRICE_ACCOUNTS: Dict[str, str] = {}
env_pyth = os.getenv("PYTH_PRICE_ACCOUNTS")
if env_pyth:
    try:
        val = json.loads(env_pyth)
        if isinstance(val, dict):
            PYTH_PRICE_ACCOUNTS = {k: v for k, v in val.items()}
    except Exception:
        PYTH_PRICE_ACCOUNTS = {}


# Logging level
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
