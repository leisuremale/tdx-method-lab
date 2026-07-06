# TDX Method Lab Project Roadmap

Goal: build a practical, manually confirmed A-share trading system from the
three TDX indicators. A good-looking backtest is not enough.

## Success Criteria

V1 can move from research to paper trading only if it satisfies all checks:

1. Uses only tradable stocks in the Feishu AI universe, excluding 688.
2. Has an explicit entry, minimum hold, exit, and blocked-segment rule.
3. Beats random same-frequency entries.
4. Survives rolling-window tests, not only a single AI bull-market sample.
5. Has segment-level evidence; weak segments are blocked.
6. Generates a current action list with manual confirmation only.

## Current Candidate

V1 is a candidate watchlist system, not an automated trading system.

Entry:

```text
low_kdj_25 = CROSS(AZ3, AZ4) AND AZ3 < 25
```

Exit framework:

```text
minimum hold = 20 trading days
then use segment policy exit
manual confirmation required before order
```

Validated segment policies are generated in:

```text
reports/v1_operational_trading_system.md
```

Portfolio/risk tests are generated in:

```text
reports/v1_portfolio_risk_backtest.md
```

Paper-trading seed log is generated in:

```text
reports/v1_paper_trading_log.csv
```

## Blocked Areas

Do not trade V1 mechanically in these segments yet:

- AI服务器
- PCB
- 算力芯片/GPU/CPU设计
- 算力/IDC/算力租赁
- 连接器
- 高速铜缆/铜连接

## Next Milestones

1. Paper trade V1 current action list for at least 20 signal events.
2. Validate the portfolio layer on a non-AI universe to measure transferability.
3. Add a disaster exit that is independent of indicator exits.
4. Compare real paper results against the rolling-window expectation.
5. Only then consider Feishu alert automation for entry/exit candidates.
