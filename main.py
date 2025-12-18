# main.py
import argparse
import time

from rpc import get_client, get_signatures, get_tx, get_mint_supply
from parse import extract_trade_from_tx, Trade
from metrics import compute_volumes, compute_age_seconds
from store import init_db, save_trade, compute_volumes_sql


def run_for_mint(mint: str, rpc_url: str, limit: int):
    client = get_client(rpc_url)

    # Initialize local SQLite store
    db = init_db("./trades.db")

    signatures = get_signatures(client, mint, limit=limit)
    trades: list[Trade] = []

    for sig_info in signatures:
        sig = sig_info["signature"]
        tx = get_tx(client, sig)
        if tx is None:        
            continue
        trade = extract_trade_from_tx(tx, mint, sig)
        if trade:
            # Persist trade (deduped by signature)
            inserted = save_trade(db, trade)
            if inserted:
                trades.append(trade)


    print(f"✅ Parsed trades: {len(trades)}")

    if not trades:
        print("No trades found for this mint in the fetched signatures.")
        return

    # ---- existing volume + age calculation ----
    # Use SQL aggregation for rolling windows (fast, avoids reprocessing)
    volumes = compute_volumes_sql(db, mint)
    age_seconds = compute_age_seconds(trades)

    print("📊 Volume summary (token units + USD where available):")
    for window, vals in volumes.items():
        token_v = vals.get("token") if isinstance(vals, dict) else vals
        usd_v = vals.get("usd") if isinstance(vals, dict) else None
        if usd_v is not None:
            print(f"  {window}: {token_v} tokens, ${usd_v:.2f} USD")
        else:
            print(f"  {window}: {token_v} tokens")

    print(f"⏱️ Token age (approx, from first trade): {age_seconds} seconds")

    # ---- NEW: mint supply ----
    supply = get_mint_supply(client, mint)

    print("🪙 Mint supply:")
    print(f"  Raw:        {supply['raw']}")
    print(f"  Decimals:   {supply['decimals']}")
    print(f"  UI amount:  {supply['ui_amount_string']}")

    # Attempt to compute market cap in USD using recent trades priced in stablecoins
    price_usd = None
    # Prefer latest trade with a stablecoin quote
    for t in reversed(trades):
        if t.price is not None and t.quote_mint is not None:
            # Check if quote is USDC/USDT by comparing against common mints in metrics
            try:
                from metrics import STABLECOIN_MINTS
                if t.quote_mint in STABLECOIN_MINTS:
                    price_usd = abs(t.price)
                    break
            except Exception:
                continue

    mcap_usd = None
    if price_usd is not None:
        try:
            ui_amount = float(supply.get("ui_amount", 0.0) or 0.0)
            mcap_usd = ui_amount * price_usd
            print(f"💰 Market cap (approx): ${mcap_usd:,.2f} USD using price ${price_usd:.6f} from recent stablecoin trade")
        except Exception:
            mcap_usd = None

    return {
        "mint": mint,
        "volumes": volumes,
        "age_seconds": age_seconds,
        "supply": supply,
    }


def main():
    parser = argparse.ArgumentParser(description="Milestone 1: mint-level volume + age (MVP).")
    parser.add_argument("--mint", required=True, help="Token mint address (contract address)")
    parser.add_argument("--rpc", default="https://api.mainnet-beta.solana.com", help="Solana RPC URL")
    parser.add_argument("--limit", type=int, default=100, help="Number of recent signatures to scan")

    args = parser.parse_args()
    res = run_for_mint(args.mint, args.rpc, args.limit)
    print(res)

if __name__ == "__main__":
    main()
