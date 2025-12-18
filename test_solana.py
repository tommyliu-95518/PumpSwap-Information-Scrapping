from solana.rpc.api import Client
from solders.pubkey import Pubkey


client = Client("https://api.mainnet-beta.solana.com")
print("RPC version:", client.get_version())

mint = Pubkey("So11111111111111111111111111111111111111112")
print("Mint:", mint)
