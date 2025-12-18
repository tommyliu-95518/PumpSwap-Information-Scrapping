# metrics.py
from typing import Iterable, Dict, Optional
import time
from parse import Trade

WINDOWS = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
}

def compute_volumes(
    trades: Iterable[Trade],
    now: Optional[int] = None,
) -> Dict[str, float]:
    """
    Simple definition: sum of |token_delta| in each time window.
    """
    now = now or int(time.time())
    vols: Dict[str, float] = {k: 0.0 for k in WINDOWS}
    for t in trades:
        age = now - t.ts
        if age < 0:
            # future block time?? just skip
            continue
        for label, secs in WINDOWS.items():
            if age <= secs:
                vols[label] += abs(t.token_delta)
    return vols


def compute_age_seconds(
    trades: Iterable[Trade],
    now: Optional[int] = None,
) -> Optional[int]:
    now = now or int(time.time())
    ts_list = [t.ts for t in trades]
    if not ts_list:
        return None
    first_ts = min(ts_list)
    return now - first_ts
