import base64
from types import SimpleNamespace

from metadata import get_token_metadata


class FakeClient:
    def __init__(self, payload_bytes: bytes):
        b64 = base64.b64encode(payload_bytes).decode()
        self._resp = SimpleNamespace(value=SimpleNamespace(data=[b64, "base64"]))

    def get_account_info(self, pda):
        return self._resp


def test_metadata_decoder_simple():
    # Construct fake metadata payload containing name and symbol as ASCII
    payload = b"\x00\x01" + b"MyTokenName" + b"\x00" + b"MTK" + b"\x00"
    client = FakeClient(payload)
    res = get_token_metadata(client, "MINTFAKE123456789012345678901234567890")
    assert res["name"] == "MyTokenName"
    assert res["symbol"] == "MTK"
