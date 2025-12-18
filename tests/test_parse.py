from parse import extract_trade_from_tx


from parse import PUMPSWAP_PROGRAM_ID


def make_tx(block_time: int, pre_amounts, post_amounts, mint: str, include_pumpswap: bool = True):
    def to_row(owner, amt):
        return {"owner": owner, "mint": mint, "uiTokenAmount": {"uiAmount": amt}}

    meta = {
        "preTokenBalances": [to_row(f"owner{i}", a) for i, a in enumerate(pre_amounts)],
        "postTokenBalances": [to_row(f"owner{i}", a) for i, a in enumerate(post_amounts)],
    }
    tx = {"blockTime": block_time, "meta": meta}

    # Include minimal transaction/message info so PumpSwap detection can match
    if include_pumpswap:
        tx["transaction"] = {"message": {"instructions": [{"programId": PUMPSWAP_PROGRAM_ID}]}}
    else:
        tx["transaction"] = {"message": {"instructions": [{"programId": "SomeOtherProgram"}]}}

    return tx


def test_extract_trade_positive_delta():
    # Include a quote mint with delta -10.0 so price = 10 / 5 = 2.0
    tx = make_tx(1_600_000_000, [10.0, 100.0], [15.0, 90.0], "MINT123", include_pumpswap=True)
    # The helper creates balances with mints: first owner0 uses MINT123, owner1 uses MINT123 as well
    # To produce a quote mint we will craft rows directly below for clarity
    tx["meta"]["preTokenBalances"] = [
        {"owner": "o0", "mint": "MINT123", "uiTokenAmount": {"uiAmount": 10.0}},
        {"owner": "o1", "mint": "QUOTE1", "uiTokenAmount": {"uiAmount": 100.0}},
    ]
    tx["meta"]["postTokenBalances"] = [
        {"owner": "o0", "mint": "MINT123", "uiTokenAmount": {"uiAmount": 15.0}},
        {"owner": "o1", "mint": "QUOTE1", "uiTokenAmount": {"uiAmount": 90.0}},
    ]
    trade = extract_trade_from_tx(tx, "MINT123", "SIG1")
    assert trade is not None
    assert trade.token_delta == 5.0
    assert trade.quote_mint == "QUOTE1"
    assert trade.quote_delta == -10.0
    assert trade.price == 2.0


def test_extract_trade_no_change():
    tx = make_tx(1_600_000_100, [5.0], [5.0], "MINT123", include_pumpswap=True)
    trade = extract_trade_from_tx(tx, "MINT123", "SIG2")
    assert trade is None


def test_non_pumpswap_transaction_is_ignored():
    tx = make_tx(1_600_000_200, [1.0], [2.0], "MINT123", include_pumpswap=False)
    trade = extract_trade_from_tx(tx, "MINT123", "SIG3")
    assert trade is None
