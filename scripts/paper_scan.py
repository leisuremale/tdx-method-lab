# -*- coding: utf-8 -*-
"""纸面交易线：每日收盘后扫描 TDX 信号，维护纸面持仓与日志，飞书【纸面】汇总。

策略参数化（data/paper_strategy.json）——统一证伪关出 V-final 后改配置即切换。
默认 V2：tianma25 观察 → 15日内 close>MA20 确认入场；min_hold 20 日；
退出=观变止盈或趋势转弱(连续2日确认)。成交价=信号次日开盘（由次日运行回填）。
不动真钱；消息前缀【纸面】。
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding="utf-8")
LAB = Path(__file__).resolve().parents[1]
SX = LAB.parent / "stock-exchange"
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(SX / "scripts"))

import numpy as np
import pandas as pd
import requests
from tdx_lab.event_engine import entry_from_event_confirm
from tdx_lab.indicators import compute_xhmain, compute_xhsub

STATE_PATH = LAB / "data" / "paper_state.json"
LOG_PATH = LAB / "reports" / "paper_log.csv"
STRATEGY_PATH = LAB / "data" / "paper_strategy.json"
DEFAULT_STRATEGY = {"name": "V2", "event": "tianma25", "confirm": "ma20", "window": 15,
                    "min_hold": 20, "exit": "v1_tp_or_td", "exit_confirm_days": 2,
                    "cooldown": 5}


def tradable_pool() -> list:
    codes = []
    for row in csv.reader(open(SX / "docs" / "ai_universe.csv", encoding="utf-8")):
        if not row or row[0].startswith("#") or row[0] == "tier":
            continue
        code, name = row[2], row[3]
        if row[5] == "1" or code.startswith(("43", "83", "87", "88", "920")) or "ST" in name:
            continue
        codes.append((code, name))
    return codes


def fetch_daily(code: str, count: int = 160) -> pd.DataFrame | None:
    sym = ("sh" if code.startswith(("6", "9")) else "sz") + code
    try:
        r = requests.get("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                         params={"param": f"{sym},day,,,{count},qfq"},
                         headers={"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"},
                         timeout=10)
        rows = (r.json().get("data", {}).get(sym, {}).get("qfqday")
                or r.json().get("data", {}).get(sym, {}).get("day") or [])
        if len(rows) < 80:
            return None
        df = pd.DataFrame([x[:6] for x in rows],
                          columns=["date", "open", "close", "high", "low", "volume"])
        return df.astype({"open": float, "close": float, "high": float,
                          "low": float, "volume": float})
    except Exception:
        return None


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def append_log(rows: list) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    new = not LOG_PATH.exists()
    with LOG_PATH.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "code", "name", "action", "price",
                                          "detail", "strategy"])
        if new:
            w.writeheader()
        w.writerows(rows)


def main() -> int:
    strategy = load_json(STRATEGY_PATH, DEFAULT_STRATEGY)
    state = load_json(STATE_PATH, {"positions": {}, "pending_buys": {}, "pending_sells": {},
                                   "exit_streak": {}, "cooldown": {}})
    today = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    log_rows, msg_lines = [], []

    for code, name in tradable_pool():
        df = fetch_daily(code)
        if df is None or df["date"].iloc[-1] < "2026-06-25":
            continue
        last_date = df["date"].iloc[-1]
        sub = compute_xhsub(df)
        main_ = compute_xhmain(df)
        c = df["close"].values
        o = df["open"].values
        n = len(c)
        ma20 = pd.Series(c).rolling(20).mean().values

        # ── 1) 回填昨日排程的成交（今日开盘价）──
        if code in state["pending_buys"]:
            state["positions"][code] = {"entry_date": last_date, "entry_price": o[-1],
                                        "name": name}
            del state["pending_buys"][code]
            log_rows.append({"date": last_date, "code": code, "name": name, "action": "BUY_FILL",
                             "price": o[-1], "detail": "次日开盘成交", "strategy": strategy["name"]})
            msg_lines.append(f"- 📥 买入成交 {name} `{code}` @ {o[-1]}")
        if code in state["pending_sells"] and code in state["positions"]:
            pos = state["positions"].pop(code)
            ret = (o[-1] / pos["entry_price"] - 1) * 100 - 0.26
            del state["pending_sells"][code]
            state["cooldown"][code] = strategy["cooldown"]
            log_rows.append({"date": last_date, "code": code, "name": name, "action": "SELL_FILL",
                             "price": o[-1], "detail": f"{ret:+.2f}% (自{pos['entry_date']})",
                             "strategy": strategy["name"]})
            msg_lines.append(f"- 📤 卖出成交 {name} `{code}` @ {o[-1]} ({ret:+.2f}%)")

        # ── 2) 持仓：退出信号判定（连续确认）──
        if code in state["positions"]:
            pos = state["positions"][code]
            hold_days = int(np.busday_count(pos["entry_date"], last_date))
            tp = not sub["hold_line"][-1]
            td = bool(main_["trend_down"][-1])
            hit = tp or td
            streak = state["exit_streak"].get(code, 0) + 1 if hit else 0
            state["exit_streak"][code] = streak
            if streak >= strategy["exit_confirm_days"] and hold_days >= strategy["min_hold"]:
                state["pending_sells"][code] = last_date
                msg_lines.append(f"- 🔔 退出信号确认 {name} `{code}`（明日开盘卖出）")
            continue

        # ── 3) 空仓：入场信号 ──
        if state["cooldown"].get(code, 0) > 0:
            state["cooldown"][code] -= 1
            continue
        az3, az4 = sub["az3"], sub["az4"]
        cross = np.zeros(n, bool)
        cross[1:] = (az3[1:] > az4[1:]) & (az3[:-1] <= az4[:-1])
        event = cross & (az3 < 25)
        confirm = c > ma20
        entry = entry_from_event_confirm(event, confirm, strategy["window"])
        if entry[-1]:
            state["pending_buys"][code] = last_date
            log_rows.append({"date": last_date, "code": code, "name": name, "action": "SIGNAL",
                             "price": c[-1], "detail": "观察+MA20确认，明日开盘买入",
                             "strategy": strategy["name"]})
            msg_lines.append(f"- ✳️ 入场信号 {name} `{code}` 收盘 {c[-1]}（明日开盘纸面买入）")
        elif event[-1]:
            log_rows.append({"date": last_date, "code": code, "name": name, "action": "OBSERVE",
                             "price": c[-1], "detail": "天马观察事件，待MA20确认",
                             "strategy": strategy["name"]})

    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    append_log(log_rows)

    held = len(state["positions"])
    print(f"扫描完成: 持仓{held} 待买{len(state['pending_buys'])} "
          f"待卖{len(state['pending_sells'])} 事件{len(log_rows)}")

    if msg_lines:
        try:
            from feishu_io import ALERT_CHAT_ID, send_chat_markdown
            import hashlib
            message = "\n".join([f"**【纸面】TDX试验线日报 {today}**", "",
                                 *msg_lines, "",
                                 "纸面交易，非实盘；策略=" + strategy["name"]])
            if ALERT_CHAT_ID:
                send_chat_markdown(ALERT_CHAT_ID, message,
                                   "tdx-paper-" + hashlib.sha256(message.encode()).hexdigest()[:20])
                print("飞书【纸面】日报已发")
        except Exception as exc:
            print(f"飞书发送失败(不影响日志): {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
