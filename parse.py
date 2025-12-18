# parse.py
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import logging


logger = logging.getLogger(__name__)


@dataclass
class Trade:
    signature: str
    ts: int             # blockTime (unix seconds)
    mint: str
    token_delta: float  # positive = net increase of this mint in tx, negative = net decrease
    # Milestone 3 fields:
    quote_mint: Optional[str] = None
    quote_delta: Optional[float] = None
    price: Optional[float] = None  # quote units per base token


PUMPSWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
# Known PumpSwap program IDs (expandable list). Milestone 2 will use these to
# detect PumpSwap swaps versus generic token transfers.
PUMPSWAP_PROGRAM_IDS = [PUMPSWAP_PROGRAM_ID]

def _find_token_balances(meta: Dict[str, Any], mint: str, key: str) -> List[Dict[str, Any]]:
    """
    meta[key] is preTokenBalances or postTokenBalances.
    Return list of {owner, amount_ui}.
    """
    rows = meta.get(key) or []
    out: List[Dict[str, Any]] = []
    for b in rows:
        if b.get("mint") != mint:
            continue
        ui_amount = 0.0
        ui_info = b.get("uiTokenAmount") or {}
        if "uiAmount" in ui_info and ui_info["uiAmount"] is not None:
            try:
                ui_amount = float(ui_info["uiAmount"])
            except (TypeError, ValueError):
                ui_amount = 0.0
        out.append(
            {
                "owner": b.get("owner"),
                "amount": ui_amount,
            }
        )
    return out


def _sum_balances_by_mint(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for b in rows:
        m = b.get("mint")
        if not m:
            continue
        ui_info = b.get("uiTokenAmount") or {}
        amt = 0.0
        if "uiAmount" in ui_info and ui_info["uiAmount"] is not None:
            try:
                amt = float(ui_info["uiAmount"])
            except (TypeError, ValueError):
                amt = 0.0
        out[m] = out.get(m, 0.0) + amt
    return out


def extract_trade_from_tx(
    tx: Dict[str, Any],
    mint: str,
    signature: str,
) -> Optional[Trade]:
    """
    MVP: Treat any change in total ui amount for this mint in the tx as "volume".
    Later we will filter to PumpSwap-only + compute quote side.
    """
    logger.debug("extract_trade_from_tx called")

    if not tx:
        return None
    
    # Milestone 2: Only return trades that appear to be PumpSwap swaps.
    # We detect PumpSwap usage via instruction program IDs and transaction logs.
    if not _tx_is_pumpswap_swap(tx):
        return None

    block_time = tx.get("blockTime")
    meta = tx.get("meta")
    if block_time is None or meta is None:
        return None

    # Sum balances by mint for pre/post so we can detect quote-side changes
    pre_rows = meta.get("preTokenBalances") or []
    post_rows = meta.get("postTokenBalances") or []

    pre_map = _sum_balances_by_mint(pre_rows)
    post_map = _sum_balances_by_mint(post_rows)

    # If no relevant balances at all, skip
    if not pre_map and not post_map:
        return None

    logger.debug("parse/extract_trade_from_tx pre_map: %s", pre_map)
    logger.debug("parse/extract_trade_from_tx post_map: %s", post_map)

    # Compute deltas per mint
    all_mints = set(pre_map.keys()) | set(post_map.keys())
    delta_map: Dict[str, float] = {}
    for m in all_mints:
        delta_map[m] = post_map.get(m, 0.0) - pre_map.get(m, 0.0)

    base_delta = delta_map.get(mint, 0.0)
    if base_delta == 0:
        return None

    # Heuristic: choose the largest non-base delta as quote side
    quote_mint = None
    quote_delta = None
    other_mints = [m for m in delta_map.keys() if m != mint]
    if other_mints:
        quote_mint = max(other_mints, key=lambda m: abs(delta_map.get(m, 0.0)))
        quote_delta = delta_map.get(quote_mint)

    # Compute price as (abs quote delta) / (abs base delta) when possible
    price = None
    try:
        if quote_delta is not None and abs(base_delta) > 0:
            price = abs(quote_delta) / abs(base_delta)
    except Exception:
        price = None

    return Trade(
        signature=signature,
        ts=int(block_time),
        mint=mint,
        token_delta=base_delta,
        quote_mint=quote_mint,
        quote_delta=quote_delta,
        price=price,
    )


def _tx_uses_program(tx: Dict[str, Any], program_id: str) -> bool:
    """
    Returns True if the transaction uses the given program id in any
    top-level or inner instruction.
    """
    # Top-level instructions
    try:
        msg = tx["transaction"]["message"]
    except KeyError:
        msg = None

    if msg:
        for ix in msg.get("instructions", []):
            pid = ix.get("programId")
            # Just in case programId is nested (rare), normalize:
            if isinstance(pid, dict):
                pid = pid.get("key")
            if pid == program_id:
                return True

    meta = tx.get("meta") or {}
    inner_list = meta.get("innerInstructions") or []
    for inner in inner_list:
        for ix in inner.get("instructions", []):
            pid = ix.get("programId")
            if isinstance(pid, dict):
                pid = pid.get("key")
            if pid == program_id:
                return True

    return False


def _tx_is_pumpswap_swap(tx: Dict[str, Any]) -> bool:
    """
    Heuristic to determine whether a transaction represents a PumpSwap swap.
    Checks top-level and inner instruction program IDs and log messages.
    """
    # Top-level instructions
    try:
        msg = tx["transaction"]["message"]
    except Exception:
        msg = None

    if msg:
        for ix in msg.get("instructions", []):
            pid = ix.get("programId") or ix.get("program")
            if isinstance(pid, dict):
                pid = pid.get("key")
            if pid in PUMPSWAP_PROGRAM_IDS:
                return True

    # Inner instructions
    meta = tx.get("meta") or {}
    inner_list = meta.get("innerInstructions") or []
    for inner in inner_list:
        for ix in inner.get("instructions", []):
            pid = ix.get("programId") or ix.get("program")
            if isinstance(pid, dict):
                pid = pid.get("key")
            if pid in PUMPSWAP_PROGRAM_IDS:
                return True

    # Logs may contain hints (program invoke or 'swap' keywords)
    logs = meta.get("logMessages") or []
    for line in logs:
        if not line:
            continue
        s = str(line).lower()
        if any(pid.lower() in s for pid in PUMPSWAP_PROGRAM_IDS):
            return True
        if "swap" in s:
            return True

    return False
