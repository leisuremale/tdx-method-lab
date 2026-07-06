# Market Regime Filter Tests

Generated: 2026-07-06 08:47:17 +0800

Basket bull definition: equal-weight AI basket index above MA60 and 60-day return > 20%.
Basket down definition: index below MA60 and 60-day return < 0.

## Overall Rolling Windows

| strategy | samples | trades | win | positive | beatBH | median_return | median_dd | median_calmar | median_vsBH |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base_combo | 366 | 714 | 64.71% | 254 | 116 | 11.29% | -17.09% | 0.70 | -34.15% |
| bull_delay_ma20 | 366 | 685 | 62.19% | 254 | 119 | 12.00% | -18.34% | 0.69 | -28.88% |
| bull_delay_ma55 | 366 | 652 | 59.51% | 258 | 125 | 13.30% | -20.03% | 0.63 | -22.91% |
| bull_no_sell_until_ma20 | 366 | 702 | 62.54% | 251 | 115 | 10.68% | -18.34% | 0.61 | -29.69% |
| no_new_entries_in_down | 366 | 532 | 62.03% | 204 | 92 | 3.71% | -15.62% | 0.17 | -39.74% |
| adaptive_shou_no_down | 366 | 525 | 60.57% | 208 | 95 | 2.85% | -16.63% | 0.08 | -37.31% |
| adaptive_ma20_no_down | 366 | 503 | 59.05% | 202 | 97 | 3.03% | -16.91% | 0.06 | -37.88% |
| adaptive_ma55_no_down | 366 | 475 | 53.68% | 199 | 100 | 3.08% | -18.12% | 0.00 | -36.72% |

## By Basket Regime

| strategy | basket_regime | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| base_combo | basket_bull | 124 | 232 | 65.09% | 85 | 35 | 14.35% | 1.02 | -50.63% |
| no_new_entries_in_down | basket_bull | 124 | 227 | 65.20% | 83 | 35 | 14.11% | 0.95 | -51.66% |
| bull_delay_ma20 | basket_bull | 124 | 210 | 58.57% | 82 | 37 | 14.59% | 0.88 | -46.38% |
| bull_delay_ma55 | basket_bull | 124 | 194 | 52.58% | 82 | 39 | 15.16% | 0.71 | -43.01% |
| adaptive_ma20_no_down | basket_bull | 124 | 205 | 58.54% | 81 | 37 | 14.11% | 0.69 | -45.51% |
| bull_no_sell_until_ma20 | basket_bull | 124 | 219 | 60.27% | 82 | 36 | 13.07% | 0.69 | -49.22% |
| base_combo | basket_neutral | 242 | 482 | 64.52% | 169 | 81 | 9.71% | 0.67 | -25.90% |
| bull_delay_ma55 | basket_neutral | 242 | 458 | 62.45% | 176 | 86 | 10.74% | 0.63 | -17.29% |
| bull_delay_ma20 | basket_neutral | 242 | 475 | 63.79% | 172 | 82 | 10.06% | 0.62 | -20.59% |
| adaptive_shou_no_down | basket_bull | 124 | 222 | 58.11% | 81 | 34 | 12.88% | 0.60 | -50.75% |
| bull_no_sell_until_ma20 | basket_neutral | 242 | 483 | 63.56% | 169 | 79 | 9.66% | 0.59 | -22.02% |
| adaptive_ma55_no_down | basket_bull | 124 | 189 | 52.38% | 81 | 39 | 14.59% | 0.46 | -43.35% |
| adaptive_shou_no_down | basket_neutral | 242 | 303 | 62.38% | 127 | 61 | 0.99% | 0.00 | -36.69% |
| adaptive_ma20_no_down | basket_neutral | 242 | 298 | 59.40% | 121 | 60 | 0.03% | 0.00 | -37.35% |
| no_new_entries_in_down | basket_neutral | 242 | 305 | 59.67% | 121 | 57 | 0.03% | 0.00 | -36.91% |
| adaptive_ma55_no_down | basket_neutral | 242 | 286 | 54.55% | 118 | 61 | 0.00% | 0.00 | -35.90% |

## Best Strategy By Segment

| segment | strategy | samples | trades | win | positive | beatBH | median_return | median_calmar | median_vsBH |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AIPC/端侧AI | bull_delay_ma55 | 12 | 25 | 68.00% | 8 | 6 | 9.34% | 0.70 | -1.81% |
| AI服务器 | base_combo | 24 | 58 | 58.62% | 14 | 8 | 3.48% | 0.25 | -24.13% |
| CPO | bull_delay_ma20 | 12 | 19 | 57.89% | 10 | 3 | 86.59% | 3.82 | -57.39% |
| HBM | adaptive_ma55_no_down | 12 | 18 | 55.55% | 9 | 3 | 27.43% | 1.77 | -47.51% |
| PCB | base_combo | 24 | 31 | 64.52% | 14 | 1 | 6.29% | 0.23 | -131.59% |
| 云计算 | adaptive_shou_no_down | 12 | 31 | 58.07% | 9 | 12 | 12.94% | 0.96 | 34.30% |
| 交换机/网络设备 | bull_delay_ma20 | 24 | 43 | 79.07% | 22 | 8 | 17.54% | 1.10 | -25.69% |
| 先进封装/封测 | adaptive_shou_no_down | 24 | 40 | 87.50% | 21 | 14 | 42.64% | 3.03 | 10.18% |
| 光模块 | bull_no_sell_until_ma20 | 30 | 50 | 56.00% | 21 | 1 | 18.42% | 1.11 | -240.14% |
| 半导体材料 | adaptive_ma55_no_down | 6 | 6 | 100.00% | 5 | 0 | 19.84% | 1.10 | -28.02% |
| 半导体设备 | base_combo | 6 | 8 | 100.00% | 6 | 1 | 15.52% | 1.00 | -47.99% |
| 大模型/AI应用/AIGC | base_combo | 24 | 64 | 76.56% | 22 | 18 | 24.31% | 1.50 | 14.84% |
| 存储芯片 | adaptive_shou_no_down | 24 | 24 | 87.50% | 15 | 3 | 14.11% | 1.04 | -129.01% |
| 服务器电源 | base_combo | 18 | 39 | 69.23% | 14 | 5 | 14.09% | 0.53 | -56.33% |
| 液冷/散热 | bull_no_sell_until_ma20 | 24 | 36 | 83.33% | 24 | 6 | 50.50% | 2.30 | -64.26% |
| 算力/IDC/算力租赁 | adaptive_shou_no_down | 24 | 38 | 63.16% | 12 | 8 | 0.80% | 0.04 | -33.06% |
| 算力芯片/GPU/CPU设计 | bull_delay_ma55 | 12 | 34 | 41.18% | 5 | 8 | -3.15% | -0.13 | 4.76% |
| 覆铜板CCL | base_combo | 18 | 20 | 95.00% | 14 | 1 | 20.95% | 2.09 | -91.89% |
| 连接器 | adaptive_ma20_no_down | 12 | 18 | 44.44% | 6 | 4 | -1.82% | -0.26 | -10.12% |
| 高速铜缆/铜连接 | base_combo | 24 | 43 | 48.84% | 8 | 5 | -4.94% | -0.20 | -21.58% |
