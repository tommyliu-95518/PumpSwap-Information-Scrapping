from fastapi.testclient import TestClient
from api import app, indexer
from parse import Trade


def test_api_memory_empty():
    client = TestClient(app)
    r = client.get("/volumes/UNKNOWN")
    assert r.status_code == 200
    data = r.json()
    assert "1m" in data and "5m" in data


def test_api_memory_with_trade():
    client = TestClient(app)
    # add a trade to global indexer
    t = Trade(signature="T1", ts=1700000000, mint="MINTAPI", token_delta=3.0)
    indexer.add_trade(t)
    r = client.get("/volumes/MINTAPI")
    assert r.status_code == 200
    data = r.json()
    assert data["1m"] >= 3.0
