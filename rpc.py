# rpc.py
from typing import List, Optional, Dict, Any
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.exceptions import SolanaRpcException  
import json
import time

DEFAULT_RPC = "https://api.mainnet-beta.solana.com"


def get_client(rpc_url: str = DEFAULT_RPC) -> Client:
    print(f"💎rpc/get_client/Client_Information :`{Client(rpc_url)}`")
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

    print(f"💎rpc/get_signatures/count`{len(sig_infos)}`")
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
                    print(f"❌ Could not serialize transaction object for {signature}")
                    return None

            return tx_dict

        except SolanaRpcException as e:
            # RPC-specific issues: log and retry with backoff
            backoff = 0.5 * (2 ** (attempt - 1))
            print(f"⚠️ RPC error in get_tx({signature}), attempt {attempt}/{max_retries}: {repr(e)}; backing off {backoff}s")
            time.sleep(backoff)

        except Exception as e:
            # Non-RPC errors: log and retry once or give up depending on attempt
            backoff = 0.5 * (2 ** (attempt - 1))
            print(f"❌ Unexpected error in get_tx({signature}), attempt {attempt}/{max_retries}: {repr(e)}; backing off {backoff}s")
            time.sleep(backoff)

    print(f"⏭️ Giving up on get_tx({signature}) after {max_retries} attempts.")
    return None


def get_mint_supply(client: Client, mint_address: str) -> Dict[str, Any]:
    mint_pk = Pubkey.from_string(mint_address)

    resp = client.get_token_supply(mint_pk)
    v = resp.value

    raw = int(v.amount)
    decimals = v.decimals
    ui_amount = v.ui_amount
    ui_amount_string = v.ui_amount_string

    print(
        f"💎rpc/get_mint_supply/mint`{mint_address}` "
        f"raw`{raw}` decimals`{decimals}` ui`{ui_amount_string}`"
    )

    return {
        "raw": raw,
        "decimals": decimals,
        "ui_amount": ui_amount,
        "ui_amount_string": ui_amount_string,
    }
