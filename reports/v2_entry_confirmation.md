# V2 Entry Confirmation Test

Generated: 2026-07-06 09:17:33 +0800

Purpose: test whether `AZ3 cross AZ4 and AZ3 < 25` should be only an observation signal.

Fixed exit for isolation: `not hold_line OR main trend_down`, minimum hold 20 trading days, exit confirmation 4 days.

Acceptance bias: prefer fewer but more robust entries if drawdown and flat/down-market behavior improve. Reject variants with too few trades.

## Top Overall Variants

| rank | strategy | samples | trades | win | positive | beatBH | median_return | median_dd | median_calmar | median_vsBH |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | obs_then_wait_muma_10d | 1176 | 2770 | 55.16% | 718 | 564 | 7.50% | -20.17% | 0.41 | -1.65% |
| 2 | obs_then_wait_muma_15d | 1176 | 2773 | 55.21% | 720 | 564 | 7.46% | -20.17% | 0.41 | -1.65% |
| 3 | obs_then_wait_ma20_15d | 1176 | 2647 | 56.10% | 737 | 589 | 6.86% | -19.02% | 0.41 | 0.06% |
| 4 | obs_then_wait_muma_5d | 1176 | 2667 | 55.12% | 715 | 561 | 7.12% | -19.67% | 0.39 | -1.85% |
| 5 | obs_then_wait_ma20_10d | 1176 | 2535 | 56.17% | 729 | 589 | 6.72% | -18.66% | 0.38 | 0.06% |
| 6 | obs_then_wait_ma20_5d | 1176 | 2248 | 57.12% | 724 | 581 | 6.18% | -17.26% | 0.36 | -0.72% |
| 7 | obs_direct | 1176 | 2800 | 55.00% | 720 | 580 | 7.11% | -21.39% | 0.35 | -0.51% |
| 8 | obs_direct_wait0 | 1176 | 2800 | 55.00% | 720 | 580 | 7.11% | -21.39% | 0.35 | -0.51% |
| 9 | obs_then_wait_caopan_15d | 1176 | 2252 | 55.24% | 693 | 567 | 3.94% | -17.01% | 0.24 | -1.46% |
| 10 | obs_then_wait_rs20_segment_10d | 1176 | 2179 | 54.89% | 682 | 533 | 4.59% | -18.24% | 0.23 | -3.88% |
| 11 | obs_then_wait_rs20_segment_15d | 1176 | 2383 | 54.72% | 674 | 539 | 4.39% | -19.29% | 0.22 | -3.58% |
| 12 | obs_then_wait_ma20_rs20_segment_15d | 1176 | 2112 | 53.84% | 645 | 531 | 2.77% | -17.02% | 0.13 | -4.09% |

## Regime Check For Top Variants

| strategy | basket_regime | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| obs_direct | basket_bull | 125 | 235 | 65.11% | 84 | 34 | 13.78% | 0.87 | -50.09% |
| obs_direct | basket_down | 59 | 155 | 43.87% | 49 | 44 | 26.96% | 1.04 | 19.00% |
| obs_direct | basket_neutral | 992 | 2410 | 54.73% | 587 | 502 | 5.48% | 0.29 | 0.49% |
| obs_direct_wait0 | basket_bull | 125 | 235 | 65.11% | 84 | 34 | 13.78% | 0.87 | -50.09% |
| obs_direct_wait0 | basket_down | 59 | 155 | 43.87% | 49 | 44 | 26.96% | 1.04 | 19.00% |
| obs_direct_wait0 | basket_neutral | 992 | 2410 | 54.73% | 587 | 502 | 5.48% | 0.29 | 0.49% |
| obs_then_wait_caopan_15d | basket_bull | 125 | 205 | 60.49% | 72 | 33 | 4.41% | 0.22 | -62.06% |
| obs_then_wait_caopan_15d | basket_down | 59 | 113 | 45.13% | 46 | 40 | 22.80% | 1.17 | 20.59% |
| obs_then_wait_caopan_15d | basket_neutral | 992 | 1934 | 55.27% | 575 | 494 | 3.06% | 0.23 | -0.23% |
| obs_then_wait_ma20_10d | basket_bull | 125 | 222 | 68.47% | 88 | 33 | 8.39% | 0.43 | -54.34% |
| obs_then_wait_ma20_10d | basket_down | 59 | 140 | 45.71% | 48 | 40 | 23.70% | 0.78 | 17.25% |
| obs_then_wait_ma20_10d | basket_neutral | 992 | 2173 | 55.59% | 593 | 516 | 6.05% | 0.34 | 2.03% |
| obs_then_wait_ma20_15d | basket_bull | 125 | 225 | 67.11% | 87 | 32 | 8.39% | 0.43 | -52.61% |
| obs_then_wait_ma20_15d | basket_down | 59 | 140 | 45.71% | 48 | 41 | 24.15% | 0.78 | 17.54% |
| obs_then_wait_ma20_15d | basket_neutral | 992 | 2282 | 55.65% | 602 | 516 | 6.18% | 0.36 | 2.01% |
| obs_then_wait_ma20_5d | basket_bull | 125 | 205 | 68.29% | 84 | 32 | 8.39% | 0.43 | -54.34% |
| obs_then_wait_ma20_5d | basket_down | 59 | 132 | 46.21% | 47 | 40 | 24.15% | 0.71 | 13.35% |
| obs_then_wait_ma20_5d | basket_neutral | 992 | 1911 | 56.67% | 593 | 509 | 5.54% | 0.32 | 1.10% |
| obs_then_wait_ma20_rs20_segment_15d | basket_bull | 125 | 184 | 63.04% | 70 | 31 | 2.74% | 0.18 | -66.38% |
| obs_then_wait_ma20_rs20_segment_15d | basket_down | 59 | 108 | 45.37% | 41 | 37 | 25.47% | 0.53 | 11.17% |
| obs_then_wait_ma20_rs20_segment_15d | basket_neutral | 992 | 1820 | 53.41% | 534 | 463 | 2.06% | 0.08 | -2.27% |
| obs_then_wait_muma_10d | basket_bull | 125 | 233 | 65.24% | 88 | 34 | 14.08% | 0.77 | -51.15% |
| obs_then_wait_muma_10d | basket_down | 59 | 152 | 46.71% | 47 | 43 | 25.19% | 1.02 | 18.20% |
| obs_then_wait_muma_10d | basket_neutral | 992 | 2385 | 54.72% | 583 | 487 | 6.18% | 0.32 | -0.65% |
| obs_then_wait_muma_15d | basket_bull | 125 | 233 | 65.24% | 88 | 34 | 14.08% | 0.77 | -51.15% |
| obs_then_wait_muma_15d | basket_down | 59 | 152 | 46.71% | 47 | 43 | 25.19% | 1.02 | 18.20% |
| obs_then_wait_muma_15d | basket_neutral | 992 | 2388 | 54.77% | 585 | 487 | 6.18% | 0.32 | -0.65% |
| obs_then_wait_muma_5d | basket_bull | 125 | 227 | 67.40% | 88 | 34 | 14.08% | 0.77 | -51.15% |
| obs_then_wait_muma_5d | basket_down | 59 | 152 | 46.71% | 47 | 43 | 25.19% | 1.02 | 18.20% |
| obs_then_wait_muma_5d | basket_neutral | 992 | 2288 | 54.46% | 580 | 484 | 6.11% | 0.29 | -0.92% |
| obs_then_wait_rs20_segment_10d | basket_bull | 125 | 190 | 64.21% | 77 | 28 | 4.65% | 0.25 | -65.70% |
| obs_then_wait_rs20_segment_10d | basket_down | 59 | 118 | 49.15% | 49 | 40 | 22.91% | 0.68 | 18.12% |
| obs_then_wait_rs20_segment_10d | basket_neutral | 992 | 1871 | 54.30% | 556 | 465 | 3.33% | 0.18 | -2.49% |
| obs_then_wait_rs20_segment_15d | basket_bull | 125 | 204 | 64.71% | 75 | 31 | 5.12% | 0.49 | -52.50% |
| obs_then_wait_rs20_segment_15d | basket_down | 59 | 126 | 46.82% | 47 | 37 | 19.36% | 0.50 | 16.51% |
| obs_then_wait_rs20_segment_15d | basket_neutral | 992 | 2053 | 54.21% | 552 | 471 | 3.34% | 0.18 | -1.89% |

## Segment Best Variant

| segment | strategy | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AIPC/端侧AI | obs_then_wait_muma_10d | 40 | 110 | 56.36% | 21 | 29 | 1.83% | 0.07 | 12.84% |
| AI服务器 | obs_direct | 80 | 187 | 54.01% | 49 | 35 | 9.37% | 0.53 | -4.21% |
| CPO | obs_direct | 40 | 97 | 61.86% | 28 | 17 | 18.85% | 1.01 | -12.88% |
| HBM | obs_then_wait_muma_10d | 40 | 91 | 58.24% | 30 | 18 | 7.47% | 0.24 | -10.40% |
| PCB | obs_then_wait_muma_10d | 66 | 131 | 44.27% | 39 | 22 | 8.45% | 0.49 | -30.39% |
| 云计算 | obs_then_wait_muma_10d | 40 | 120 | 49.17% | 21 | 31 | 1.92% | 0.09 | 17.63% |
| 交换机/网络设备 | obs_direct | 66 | 169 | 57.40% | 40 | 32 | 4.99% | 0.28 | -1.75% |
| 先进封装/封测 | obs_direct | 80 | 208 | 71.63% | 55 | 59 | 17.11% | 1.31 | 14.80% |
| 光模块 | obs_then_wait_muma_10d | 100 | 215 | 53.02% | 57 | 27 | 10.95% | 0.35 | -42.53% |
| 半导体材料 | obs_then_wait_rs20_segment_10d | 20 | 36 | 55.56% | 12 | 8 | 4.20% | 0.36 | -14.38% |
| 半导体设备 | obs_direct | 20 | 40 | 37.50% | 9 | 1 | -9.35% | -0.57 | -25.86% |
| 大模型/AI应用/AIGC | obs_direct | 80 | 233 | 48.50% | 44 | 55 | 1.74% | 0.09 | 11.43% |
| 存储芯片 | obs_then_wait_muma_10d | 67 | 153 | 60.78% | 44 | 36 | 14.08% | 0.90 | 2.15% |
| 服务器电源 | obs_direct | 60 | 146 | 56.16% | 38 | 27 | 12.46% | 0.44 | -9.19% |
| 液冷/散热 | obs_direct | 77 | 175 | 58.86% | 63 | 30 | 15.56% | 0.70 | -7.44% |
| 算力/IDC/算力租赁 | obs_then_wait_muma_15d | 80 | 205 | 50.73% | 44 | 36 | 5.73% | 0.32 | -3.44% |
| 算力芯片/GPU/CPU设计 | obs_then_wait_muma_10d | 40 | 108 | 53.70% | 26 | 31 | 11.15% | 0.48 | 16.80% |
| 覆铜板CCL | obs_direct | 60 | 130 | 62.31% | 35 | 33 | 6.75% | 0.43 | 1.55% |
| 连接器 | obs_direct | 40 | 82 | 54.88% | 21 | 21 | 0.44% | 0.06 | 0.78% |
| 高速铜缆/铜连接 | obs_then_wait_muma_10d | 80 | 182 | 54.40% | 53 | 37 | 6.22% | 0.30 | -3.70% |

## Working Conclusion

- The low-position KDJ cross is now treated as an observation event.
- Preferred next candidate: `obs_then_wait_ma20_15d`. It keeps enough trades, improves median drawdown versus direct observation, and is the only top-three variant with non-negative median vs buy-hold.
- `obs_then_wait_muma_10d` has slightly better median return/Calmar, but `mu_ma` is effectively `close > EMA10`; MA20 confirmation is simpler and less likely to be formula-specific overfit.
- Relative-strength filters are not accepted yet: they reduce trades and did not improve overall robustness in this run.
