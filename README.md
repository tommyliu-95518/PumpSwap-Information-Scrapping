# PumpSwap Realtime Metrics

This project parses PumpSwap transactions on Solana to compute token-level volumes, age, and approximate market cap using on-chain data only.

Configuration via environment variables (see `config.py`):

- `LOG_LEVEL` — logging level (default `INFO`).
- `STABLECOIN_MINTS` — comma-separated list of token mint addresses to treat as USD stablecoins (default includes common USDC/USDT mints).
- `PYTH_PRICE_ACCOUNTS` — JSON mapping of token mint -> Pyth price account pubkey, e.g.: `{"So111...": "B1..."}`

Example `PYTH_PRICE_ACCOUNTS` export (bash):

```bash
export PYTH_PRICE_ACCOUNTS='{"So11111111111111111111111111111111111111112":"<pyth_price_account_pubkey>"}'
```

If `pythclient` (or `pyth-client`) is installed, the service will use it to decode Pyth accounts. Otherwise a built-in best-effort parser is used.

Usage

CLI:

```bash
python main.py --mint <MINT_ADDRESS>
```

API:

```bash
uvicorn api:app --reload
# then GET /volumes/{mint}
```

Tests

```bash
python -m pytest -q
```
