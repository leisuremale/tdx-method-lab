# Operational Trading System V1

Generated: 2026-07-06 08:54:32 +0800

Objective: find a practical trading system, not a pretty backtest.

## System Status

Verdict: candidate system only. It is usable for watchlist and manual confirmation, not yet for automatic execution.

Core rule:

1. Trade only validated segments.
2. Entry is low KDJ restart: AZ3 crosses above AZ4 while AZ3 < 25.
3. Minimum hold: 20 trading days.
4. Exit uses the segment policy selected from rolling-window tests.
5. All orders require manual confirmation.

## Validated Segment Policies

| segment | policy |
|---|---|
| 先进封装/封测 | adaptive_shou_no_down |
| 大模型/AI应用/AIGC | base_combo |
| 液冷/散热 | bull_no_sell_until_ma20 |
| CPO | bull_delay_ma20 |
| HBM | adaptive_ma55_no_down |
| 交换机/网络设备 | bull_delay_ma20 |
| 覆铜板CCL | base_combo |

## Rolling Window Result For Segment Policy

| samples | trades | win | positive | beatBH | median_return | median_dd | median_calmar | median_vsBH |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 138 | 240 | 78.33% | 122 | 53 | 22.81% | -17.11% | 1.66 | -18.09% |

## Current Action List

| action | code | name | segment | policy | date | close | reason | state | basket_down |
|---|---|---|---|---|---:|---:|---|---|---:|
| entry_candidate | 002230 | 科大讯飞 | 大模型/AI应用/AIGC | base_combo | 2026-07-03 | 41.51 | low_kdj_25_entry | 持股 | 0 |
| entry_candidate | 601360 | 三六零 | 大模型/AI应用/AIGC | base_combo | 2026-07-03 | 8.71 | low_kdj_25_entry | 持股 | 0 |
| exit_condition | 300757 | 罗博特科 | CPO | bull_delay_ma20 | 2026-07-03 | 512.73 | bull_delay_ma20_exit_condition | 止盈 | 0 |
| exit_condition | 300624 | 万兴科技 | 大模型/AI应用/AIGC | base_combo | 2026-07-03 | 50.61 | base_combo_exit_condition | 止盈 | 0 |
| exit_condition | 002837 | 英维克 | 液冷/散热 | bull_no_sell_until_ma20 | 2026-07-03 | 71.43 | bull_no_sell_until_ma20_exit_condition | 止盈 | 0 |
| exit_condition | 300499 | 高澜股份 | 液冷/散热 | bull_no_sell_until_ma20 | 2026-07-03 | 36.6 | bull_no_sell_until_ma20_exit_condition | 止盈 | 0 |
| exit_condition | 002636 | 金安国纪 | 覆铜板CCL | base_combo | 2026-07-03 | 106.95 | base_combo_exit_condition | 止盈 | 0 |
| exit_condition | 600183 | 生益科技 | 覆铜板CCL | base_combo | 2026-07-03 | 160.78 | base_combo_exit_condition | 止盈 | 0 |
| exit_condition | 603186 | 华正新材 | 覆铜板CCL | base_combo | 2026-07-03 | 199.99 | base_combo_exit_condition | 止盈 | 0 |
| watch | 300570 | 太辰光 | CPO | bull_delay_ma20 | 2026-07-03 | 237.12 | validated_segment | 止盈 | 0 |
| watch | 002409 | 雅克科技 | HBM | adaptive_ma55_no_down | 2026-07-03 | 199.5 | validated_segment | 止盈 | 0 |
| watch | 300475 | 香农芯创 | HBM | adaptive_ma55_no_down | 2026-07-03 | 264.25 | validated_segment | 止盈 | 0 |
| watch | 000938 | 紫光股份(新华三) | 交换机/网络设备 | bull_delay_ma20 | 2026-07-03 | 30.28 | validated_segment | 持股 | 0 |
| watch | 002396 | 星网锐捷 | 交换机/网络设备 | bull_delay_ma20 | 2026-07-03 | 23.4 | validated_segment | 持股 | 0 |
| watch | 301165 | 锐捷网络 | 交换机/网络设备 | bull_delay_ma20 | 2026-07-03 | 94.89 | validated_segment | 持股 | 0 |
| watch | 301191 | 菲菱科思 | 交换机/网络设备 | bull_delay_ma20 | 2026-07-03 | 112.51 | validated_segment | 持股 | 0 |
| watch | 002156 | 通富微电 | 先进封装/封测 | adaptive_shou_no_down | 2026-07-03 | 64.8 | validated_segment | 止盈 | 0 |
| watch | 002185 | 华天科技 | 先进封装/封测 | adaptive_shou_no_down | 2026-07-03 | 19.51 | validated_segment | 止盈 | 0 |
| watch | 600584 | 长电科技 | 先进封装/封测 | adaptive_shou_no_down | 2026-07-03 | 90.88 | validated_segment | 止盈 | 0 |
| watch | 603005 | 晶方科技 | 先进封装/封测 | adaptive_shou_no_down | 2026-07-03 | 43.38 | validated_segment | 止盈 | 0 |
| watch | 300418 | 昆仑万维 | 大模型/AI应用/AIGC | base_combo | 2026-07-03 | 42.66 | validated_segment | 持股 | 0 |
| watch | 002272 | 川润股份 | 液冷/散热 | bull_no_sell_until_ma20 | 2026-07-03 | 23.26 | validated_segment | 止盈 | 0 |
| watch | 301018 | 申菱环境 | 液冷/散热 | bull_no_sell_until_ma20 | 2026-07-03 | 117.78 | validated_segment | 持股 | 0 |
| ignore | 002405 | 四维图新 | AIPC/端侧AI |  | 2026-07-03 | 6.56 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 300496 | 中科创达 | AIPC/端侧AI |  | 2026-07-03 | 62.7 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 000034 | 神州数码 | AI服务器 |  | 2026-07-03 | 27.97 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 000977 | 浪潮信息 | AI服务器 |  | 2026-07-03 | 66.35 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 601138 | 工业富联 | AI服务器 |  | 2026-07-03 | 64.72 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 603019 | 中科曙光 | AI服务器 |  | 2026-07-03 | 92.68 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 001389 | 广合科技 | PCB |  | 2026-07-03 | 203.0 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 002463 | 沪电股份 | PCB |  | 2026-07-03 | 135.35 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 002916 | 深南电路 | PCB |  | 2026-07-03 | 454.48 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 300476 | 胜宏科技 | PCB |  | 2026-07-03 | 308.07 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 600588 | 用友网络 | 云计算 |  | 2026-07-03 | 9.31 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 600845 | 宝信软件 | 云计算 |  | 2026-07-03 | 18.25 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 002281 | 光迅科技 | 光模块 |  | 2026-07-03 | 217.33 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 300308 | 中际旭创 | 光模块 |  | 2026-07-03 | 1116.0 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 300394 | 天孚通信 | 光模块 |  | 2026-07-03 | 250.1 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 300502 | 新易盛 | 光模块 |  | 2026-07-03 | 526.0 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 603083 | 剑桥科技 | 光模块 |  | 2026-07-03 | 209.37 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 300054 | 鼎龙股份 | 半导体材料 |  | 2026-07-03 | 89.88 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 002371 | 北方华创 | 半导体设备 |  | 2026-07-03 | 816.0 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 001309 | 德明利 | 存储芯片 |  | 2026-07-03 | 881.91 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 300223 | 北京君正 | 存储芯片 |  | 2026-07-03 | 259.56 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 301308 | 江波龙 | 存储芯片 |  | 2026-07-03 | 618.02 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 603986 | 兆易创新 | 存储芯片 |  | 2026-07-03 | 677.77 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 002843 | 泰嘉股份 | 服务器电源 |  | 2026-07-03 | 23.53 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 002851 | 麦格米特 | 服务器电源 |  | 2026-07-03 | 147.62 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 300870 | 欧陆通 | 服务器电源 |  | 2026-07-03 | 295.9 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 300383 | 光环新网 | 算力/IDC/算力租赁 |  | 2026-07-03 | 13.0 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 300442 | 润泽科技 | 算力/IDC/算力租赁 |  | 2026-07-03 | 85.44 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 300846 | 首都在线 | 算力/IDC/算力租赁 |  | 2026-07-03 | 20.54 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 600602 | 云赛智联 | 算力/IDC/算力租赁 |  | 2026-07-03 | 16.01 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 300474 | 景嘉微 | 算力芯片/GPU/CPU设计 |  | 2026-07-03 | 57.23 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 603501 | 韦尔股份(豪威) | 算力芯片/GPU/CPU设计 |  | 2026-07-03 | 102.3 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 002179 | 中航光电 | 连接器 |  | 2026-07-03 | 42.35 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 002475 | 立讯精密 | 连接器 |  | 2026-07-03 | 64.44 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 002130 | 沃尔核材 | 高速铜缆/铜连接 |  | 2026-07-03 | 18.28 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 300563 | 神宇股份 | 高速铜缆/铜连接 |  | 2026-07-03 | 27.8 | segment_blocked_or_unvalidated | 持股 | 0 |
| ignore | 300913 | 兆龙互连 | 高速铜缆/铜连接 |  | 2026-07-03 | 41.49 | segment_blocked_or_unvalidated | 止盈 | 0 |
| ignore | 600577 | 精达股份 | 高速铜缆/铜连接 |  | 2026-07-03 | 9.69 | segment_blocked_or_unvalidated | 持股 | 0 |

## Blocked Segments

Do not trade V1 mechanically in these segments until a separate edge is found:

- AI服务器
- PCB
- 算力/IDC/算力租赁
- 算力芯片/GPU/CPU设计
- 连接器
- 高速铜缆/铜连接
