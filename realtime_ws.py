import asyncio
import json
import time
from typing import Optional

import websockets
from solana.rpc.api import Client

from parse import extract_trade_from_tx
from realtime import InMemoryIndexer
from store import init_db, save_trade

DEFAULT_WS = "wss://api.mainnet-beta.solana.com/"
DEFAULT_RPC = "https://api.mainnet-beta.solana.com"
PUMPSWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"


class PumpSwapSubscriber:
    def __init__(self, ws_url: str = DEFAULT_WS, rpc_url: str = DEFAULT_RPC, program_id: str = PUMPSWAP_PROGRAM_ID):
        self.ws_url = ws_url
        self.rpc_url = rpc_url
        self.program_id = program_id
        self.client = Client(rpc_url)
        self.indexer = InMemoryIndexer()
        self.db = init_db("./trades.db")
        self._running = False

    async def _subscribe(self, websocket):
        # logsSubscribe with mentions filter
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "logsSubscribe",
            "params": ["all", {"mentions": [self.program_id]}],
        }
        await websocket.send(json.dumps(req))

    async def _handle_message(self, msg: str):
        try:
            payload = json.loads(msg)
        except Exception:
            return

        # notifications come in as {"jsonrpc":"2.0","method":"logsNotification","params":{...}}
        params = payload.get("params")
        if not params:
            return
        result = params.get("result") or {}
        sig = result.get("signature")
        if not sig:
            return

        # fetch transaction via HTTP RPC and parse
        try:
            tx = self.client.get_transaction(sig, encoding="jsonParsed", max_supported_transaction_version=0)
            tx_obj = tx.value
            if tx_obj is None:
                return
            # try to convert to dict-like
            try:
                tx_json = tx_obj.to_json()
                tx_dict = json.loads(tx_json)
            except Exception:
                try:
                    tx_dict = dict(tx_obj)
                except Exception:
                    return

            trade = extract_trade_from_tx(tx_dict, None, sig) if False else None
            # We need to know which mint to check; instead, try to extract trades for known mints by
            # scanning pre/post balances and returning Trade for any mint used by PumpSwap.
            # Reuse extract_trade_from_tx by iterating over mints found in pre/post.
            meta = tx_dict.get("meta") or {}
            pre = meta.get("preTokenBalances") or []
            post = meta.get("postTokenBalances") or []
            mints = set()
            for r in pre + post:
                if r.get("mint"):
                    mints.add(r.get("mint"))

            for mint in mints:
                trade = extract_trade_from_tx(tx_dict, mint, sig)
                if trade:
                    # add to in-memory indexer and persist
                    self.indexer.add_trade(trade)
                    save_trade(self.db, trade)

        except Exception:
            return

    async def run(self):
        self._running = True
        backoff = 1
        while self._running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    await self._subscribe(ws)
                    backoff = 1
                    async for message in ws:
                        await self._handle_message(message)
                        if not self._running:
                            break
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    def stop(self):
        self._running = False


def start_background():
    sub = PumpSwapSubscriber()
    loop = asyncio.get_event_loop()
    loop.create_task(sub.run())
    return sub

if __name__ == "__main__":
    # simple runner
    sub = PumpSwapSubscriber()
    try:
        asyncio.run(sub.run())
    except KeyboardInterrupt:
        sub.stop()
