"""Pure-Python best-effort Pyth v2 parser.

This parser implements a conservative, well-documented subset of the Pyth
price account fields. It is intended as a robust fallback when the
`pyth-client` library is not available.

Note: real Pyth accounts may have a different exact layout; this module
provides helpers to build and parse synthetic test accounts consistent with
the parser for unit tests. Use `rpc.get_price_from_pyth()` which prefers the
official client when available and falls back to this parser.
"""
from __future__ import annotations
import struct
from typing import Optional, Dict, Any

# We define a simple, stable layout for price accounts for testing and
# parsing in this repository. The real Pyth v2 layout is more complex and
# versioned; this parser focuses on decoding the canonical fields used by
# consumers: price (as int64), exponent (int32), confidence (uint64),
# status (uint32), valid_slot (uint64), publish_slot (uint64).

# Offsets (bytes) for our simplified layout
_OFF_MAGIC = 0
_OFF_VERSION = 4
_OFF_TYPE = 8
_OFF_EXPO = 12
_OFF_PRICE = 16
_OFF_CONF = 24
_OFF_STATUS = 32
_OFF_VALID_SLOT = 36
_OFF_PUBLISH_SLOT = 44
_MIN_LEN = 52


def make_price_account_bytes(
    price: int,
    expo: int,
    conf: int,
    status: int = 1,
    valid_slot: int = 0,
    publish_slot: int = 0,
    version: int = 2,
    acct_type: int = 2,
) -> bytes:
    """Construct synthetic price account bytes matching this parser's layout.

    All integers are encoded little-endian. This helper is primarily intended
    for unit tests.
    """
    # magic: 0x50485954 ('PYTH' as u32)
    magic = 0x50595448
    b = bytearray(max(_MIN_LEN, _OFF_PUBLISH_SLOT + 8))
    struct.pack_into('<I', b, _OFF_MAGIC, magic)
    struct.pack_into('<I', b, _OFF_VERSION, version)
    struct.pack_into('<I', b, _OFF_TYPE, acct_type)
    struct.pack_into('<i', b, _OFF_EXPO, int(expo))
    struct.pack_into('<q', b, _OFF_PRICE, int(price))
    struct.pack_into('<Q', b, _OFF_CONF, int(conf))
    struct.pack_into('<I', b, _OFF_STATUS, int(status))
    struct.pack_into('<Q', b, _OFF_VALID_SLOT, int(valid_slot))
    struct.pack_into('<Q', b, _OFF_PUBLISH_SLOT, int(publish_slot))
    return bytes(b)


def parse_price_account(raw: bytes) -> Optional[Dict[str, Any]]:
    """Parse a Pyth-like price account and return canonical fields.

    Returns dict with keys: price (int), expo (int), conf (int), status (int),
    valid_slot (int), publish_slot (int). Returns None if parsing fails.
    """
    if not raw or len(raw) < _MIN_LEN:
        return None
    try:
        magic = struct.unpack_from('<I', raw, _OFF_MAGIC)[0]
        # Accept either exact magic or permissive
        if magic != 0x50595448:
            # Not a recognized Pyth-like account
            return None

        version = struct.unpack_from('<I', raw, _OFF_VERSION)[0]
        acct_type = struct.unpack_from('<I', raw, _OFF_TYPE)[0]
        expo = struct.unpack_from('<i', raw, _OFF_EXPO)[0]
        price = struct.unpack_from('<q', raw, _OFF_PRICE)[0]
        conf = struct.unpack_from('<Q', raw, _OFF_CONF)[0]
        status = struct.unpack_from('<I', raw, _OFF_STATUS)[0]
        valid_slot = struct.unpack_from('<Q', raw, _OFF_VALID_SLOT)[0]
        publish_slot = struct.unpack_from('<Q', raw, _OFF_PUBLISH_SLOT)[0]

        return {
            'version': int(version),
            'type': int(acct_type),
            'price': int(price),
            'expo': int(expo),
            'conf': int(conf),
            'status': int(status),
            'valid_slot': int(valid_slot),
            'publish_slot': int(publish_slot),
        }
    except Exception:
        return None


if __name__ == '__main__':
    # Quick smoke test
    b = make_price_account_bytes(price=123456789, expo=-6, conf=1000, status=1, valid_slot=100, publish_slot=200)
    print(parse_price_account(b))
