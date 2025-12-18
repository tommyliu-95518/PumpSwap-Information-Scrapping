# main.py
import argparse
import time

from rpc import get_client, get_signatures, get_tx, get_mint_supply
from parse import extract_trade_from_tx, Trade
from metrics import compute_volumes, compute_age_seconds


def run_for_mint(mint: str, rpc_url: str, limit: int):
    client = get_client(rpc_url)

    signatures = get_signatures(client, mint, limit=limit)
    trades: list[Trade] = []

    for sig_info in signatures:
        sig = sig_info["signature"]
        tx = get_tx(client, sig)
        if tx is None:        
            continue
        trade = extract_trade_from_tx(tx, mint, sig)
        if trade:
            trades.append(trade)


    print(f"✅ Parsed trades: {len(trades)}")

    if not trades:
        print("No trades found for this mint in the fetched signatures.")
        return

    # ---- existing volume + age calculation ----
    volumes = compute_volumes(trades)
    age_seconds = compute_age_seconds(trades)

    print("📊 Volume summary:")
    for window, vol in volumes.items():
        print(f"  {window}: {vol}")

    print(f"⏱️ Token age (approx, from first trade): {age_seconds} seconds")

    # ---- NEW: mint supply ----
    supply = get_mint_supply(client, mint)

    print("🪙 Mint supply:")
    print(f"  Raw:        {supply['raw']}")
    print(f"  Decimals:   {supply['decimals']}")
    print(f"  UI amount:  {supply['ui_amount_string']}")

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
