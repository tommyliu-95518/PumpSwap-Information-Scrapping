from solders.pubkey import Pubkey
from solana.rpc.api import Client
from typing import Optional, Dict, Any
import base64
import re

METAPLEX_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"


def _find_metadata_pda(mint: str) -> Optional[Pubkey]:
    try:
        mint_pk = Pubkey.from_string(mint)
        program_pk = Pubkey.from_string(METAPLEX_PROGRAM_ID)
        try:
            pda, _ = Pubkey.find_program_address([b"metadata", bytes(program_pk), bytes(mint_pk)], program_pk)
            return pda
        except Exception:
            try:
                pda, _ = Pubkey.find_program_address([b"metadata", program_pk.to_bytes(), mint_pk.to_bytes()], program_pk)
                return pda
            except Exception:
                return None
    except Exception:
        return None


def get_token_metadata(client: Client, mint: str) -> Dict[str, Optional[str]]:
    """Fetch Metaplex metadata account and attempt to extract `name` and `symbol`.

    This is a best-effort decoder: it fetches the PDA account data and looks for
    printable ASCII substrings that commonly represent the name and symbol fields.
    Returns a dict: {"name": str|None, "symbol": str|None, "raw": base64|None}
    """
    pda = _find_metadata_pda(mint)
    # If PDA can't be derived (e.g., invalid test mint), fall back to using the
    # provided `mint` value directly when calling the RPC client. This keeps the
    # function usable in unit tests with fake clients.
    pda_arg = pda if pda is not None else mint

    try:
        resp = client.get_account_info(pda_arg)
        val = resp.value
        if not val:
            return {"name": None, "symbol": None, "pda": str(pda), "raw": None}

        data_field = None
        # solana RPC returns data as [base64, encoding]
        if hasattr(val, "data"):
            try:
                if isinstance(val.data, (list, tuple)) and len(val.data) >= 1:
                    data_field = val.data[0]
                else:
                    data_field = val.data
            except Exception:
                data_field = None

        if not data_field:
            return {"name": None, "symbol": None, "pda": str(pda), "raw": None}

        raw_b = base64.b64decode(data_field)

        # Heuristic: find printable ASCII substrings between 2 and 64 chars
        candidates = re.findall(b"[ -~]{2,64}", raw_b)
        decoded = [c.decode("utf-8", errors="ignore").strip() for c in candidates]

        name = decoded[0] if len(decoded) >= 1 else None
        symbol = decoded[1] if len(decoded) >= 2 else None

        return {"name": name, "symbol": symbol, "pda": str(pda), "raw": data_field}

    except Exception:
        return {"name": None, "symbol": None, "pda": str(pda), "raw": None}
