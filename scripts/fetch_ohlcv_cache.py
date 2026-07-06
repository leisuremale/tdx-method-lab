# -*- coding: utf-8 -*-
"""统一证伪关数据层：400 只 survivorship-correct 池的 OHLCV 日线（含成交量）。

复用 stock-exchange 的池定义与断点续跑模式；baostock 串行。
产出 reports/../data/ohlcv_cache/{bao_code}.csv: date,open,high,low,close,volume
"""
from __future__ import annotations
import json, os, sys, time

sys.stdout.reconfigure(encoding="utf-8")
LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SX = os.path.join(os.path.dirname(LAB), "stock-exchange")
CACHE = os.path.join(LAB, "data", "ohlcv_cache")
START, END = "2021-01-04", "2026-07-04"


def main() -> int:
    import baostock as bs
    os.makedirs(CACHE, exist_ok=True)
    uni = json.load(open(os.path.join(SX, "output", "universe_free.json"), encoding="utf-8"))
    bs.login()
    ok = miss = skip = 0
    try:
        for i, code in enumerate(sorted(uni), 1):
            path = os.path.join(CACHE, f"{code}.csv")
            if os.path.exists(path):
                skip += 1
                continue
            r = bs.query_history_k_data_plus(code, "date,open,high,low,close,volume",
                                             start_date=START, end_date=END,
                                             frequency="d", adjustflag="2")
            rows = []
            while r.error_code == "0" and r.next():
                rows.append(r.get_row_data())
            if len(rows) > 120:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("date,open,high,low,close,volume\n")
                    for x in rows:
                        f.write(",".join(x) + "\n")
                ok += 1
            else:
                miss += 1
            if i % 50 == 0:
                print(f"  {i}/{len(uni)} ok={ok} miss={miss} skip={skip}", flush=True)
            time.sleep(0.05)
    finally:
        bs.logout()
    print(f"DONE ohlcv cache: ok={ok} miss={miss} skip={skip} -> {CACHE}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
