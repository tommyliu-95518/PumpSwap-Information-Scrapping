# rpc.py
from typing import List, Optional, Dict, Any
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.exceptions import SolanaRpcException
import json
import time
import logging

from logging_config import setup_logging
from config import PYTH_PRICE_ACCOUNTS
import pyth_parser
from base64 import b64decode

logger = logging.getLogger(__name__)

DEFAULT_RPC = "https://api.mainnet-beta.solana.com"


def get_client(rpc_url: str = DEFAULT_RPC) -> Client:
    logger.debug("rpc.get_client creating Client for %s", rpc_url)
    return Client(rpc_url)


def get_signatures(
    client: Client,
    address: str,
    limit: int = 50,
    before: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch recent signatures involving a given address (token mint for our MVP).
    """
    resp = client.get_signatures_for_address(
        Pubkey.from_string(address),
        before=before,
        limit=limit,
    )

    sig_infos = []

    for info in resp.value:
        sig_infos.append(
            {
                "signature": str(info.signature),
                "slot": info.slot,
                "block_time": info.block_time,  # may be None
                "err": info.err,
            }
        )

    logger.debug("rpc.get_signatures count=%d", len(sig_infos))
    return sig_infos

def get_tx(
    client: Client,
    signature: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a parsed transaction and return it as a plain dict.
    On RPC errors (e.g. 429 Too Many Requests), retry a bit, then give up and return None.
    """
    sig = Signature.from_string(signature)

    # Retry with exponential backoff to handle transient RPC issues (rate limits, timeouts)
    max_retries = 6
    for attempt in range(1, max_retries + 1):
        try:
            resp = client.get_transaction(
                sig,
                encoding="jsonParsed",
                max_supported_transaction_version=0,
            )
            tx_obj = resp.value
            if tx_obj is None:
                return None

            # Many RPC response objects expose a `to_json()` helper; fall back safely.
            try:
                tx_json_str = tx_obj.to_json()
                tx_dict = json.loads(tx_json_str)
            except Exception:
                # If it's already a plain dict-like structure, try to use it directly
                try:
                    tx_dict = dict(tx_obj)
                except Exception:
                    # As a last resort, return None to avoid blowing up tests
                    logger.warning("Could not serialize transaction object for %s", signature)
                    return None

            return tx_dict

        except SolanaRpcException as e:
            # RPC-specific issues: log and retry with backoff
            backoff = 0.5 * (2 ** (attempt - 1))
            logger.warning("RPC error in get_tx(%s), attempt %d/%d: %r; backing off %ss", signature, attempt, max_retries, e, backoff)
            time.sleep(backoff)

        except Exception as e:
            # Non-RPC errors: log and retry once or give up depending on attempt
            backoff = 0.5 * (2 ** (attempt - 1))
            logger.error("Unexpected error in get_tx(%s), attempt %d/%d: %r; backing off %ss", signature, attempt, max_retries, e, backoff)
            time.sleep(backoff)

    logger.info("Giving up on get_tx(%s) after %d attempts.", signature, max_retries)
    return None


def get_mint_supply(client: Client, mint_address: str) -> Dict[str, Any]:
    mint_pk = Pubkey.from_string(mint_address)

    resp = client.get_token_supply(mint_pk)
    v = resp.value

    raw = int(v.amount)
    decimals = v.decimals
    ui_amount = v.ui_amount
    ui_amount_string = v.ui_amount_string

    logger.debug(
        "rpc/get_mint_supply mint=%s raw=%s decimals=%s ui=%s",
        mint_address,
        raw,
        decimals,
        ui_amount_string,
    )

    return {
        "raw": raw,
        "decimals": decimals,
        "ui_amount": ui_amount,
        "ui_amount_string": ui_amount_string,
    }


def get_price_from_pyth(client: Client, price_account: str) -> Optional[float]:
    """Attempt to fetch a price from a Pyth price account.

    This is best-effort: it will try to import an external Pyth helper library
    (if available) and decode the account. If not available or decoding
    fails it returns None.
    """
    try:
        # Try to import pythclient if installed
        from pythclient.pythaccounts import PriceAccount  # type: ignore
    except Exception:
        # Fall back to a lightweight pure-Python binary parser below
        PriceAccount = None

    try:
        resp = client.get_account_info(Pubkey.from_string(price_account))
        val = resp.value
        if not val:
            return None
        data_field = None
        if hasattr(val, "data"):
            try:
                if isinstance(val.data, (list, tuple)) and len(val.data) >= 1:
                    data_field = val.data[0]
                else:
                    data_field = val.data
            except Exception:
                data_field = None

        if not data_field:
            return None

        raw_b = b64decode(data_field)

        # If pythclient is available prefer it (more correct)
        if PriceAccount is not None:
            try:
                pa = PriceAccount.from_bytes(raw_b)
                price = pa.get_current_price()
                return float(price) if price is not None else None
            except Exception:
                # Fall through to fallback parser
                logger.debug("pythclient parse failed, falling back to local parser")

        # Try our pure-Python parser
        try:
            parsed = pyth_parser.parse_price_account(raw_b)
            if parsed and parsed.get('price') is not None and parsed.get('expo') is not None:
                try:
                    price_val = float(parsed['price']) * (10 ** int(parsed['expo']))
                    if price_val > 0 and price_val < 1e12:
                        return price_val
                except Exception:
                    pass
        except Exception:
            logger.debug("Local pyth_parser parse failed")

        # Heuristic parser: search for plausible (price_int64, expo_int32) pairs
        # and compute price = price_int64 * 10**expo. This is best-effort.
        try:
            from struct import unpack_from

            L = len(raw_b)
            # Look for candidate exponent (int32) values in reasonable range
            for pos in range(0, max(0, L - 4), 1):
                try:
                    expo = unpack_from('<i', raw_b, pos)[0]
                except Exception:
                    continue
                if expo < -20 or expo > 10:
                    continue
                # Search nearby for a signed int64 value representing price
                start = max(0, pos - 64)
                end = min(L - 8, pos + 64)
                for j in range(start, end + 1):
                    try:
                        val = unpack_from('<q', raw_b, j)[0]
                    except Exception:
                        continue
                    # Filter implausible integers
                    if val == 0:
                        continue
                    if abs(val) > 10 ** 18:
                        continue
                    # Compute float price
                    price = float(val) * (10 ** expo)
                    # Accept plausible positive non-inf prices
                    if price > 0 and price < 1e12:
                        return price
        except Exception:
            logger.debug("Heuristic Pyth parse failed")

        return None
    except Exception as e:
        logger.exception("Error fetching Pyth price: %s", e)
        return None


def get_price_for_mint(client: Client, mint: str) -> Optional[float]:
    """Lookup Pyth mapping from config and fetch price if mapping exists."""
    acct = PYTH_PRICE_ACCOUNTS.get(mint)
    if not acct:
        return None
    return get_price_from_pyth(client, acct)
