# Day3 Edge Summary: BTC, ETH, ADA, LINK, LTC

Data uses Binance 1-hour candles rebuilt into UTC daily candles.
All tests are Day3-only. No Day4 extension is allowed.

Definitions:
- Bullish sweep reclaim: Day2 low < Day1 low and Day2 close > Day1 low.
- Bullish displacement: Day2 close > Day1 high, with no body-size or close-position filter.
- Target-before-opposing means Day3 reaches target before the opposing side on 1-hour sequence.

## Comparison

| Symbol | Sweep Events | Sweep T1 Before Opposing | Sweep Opposing Before T1 | Displacement Events | Displacement T1 Before Opposing | Displacement Opposing Before T1 |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 742 | 50.94% | 26.15% | 771 | 64.33% | 13.36% |
| ETH | 715 | 50.63% | 26.85% | 743 | 63.8% | 15.07% |
| ADA | 672 | 52.53% | 27.83% | 627 | 65.55% | 13.72% |
| LINK | 573 | 54.62% | 24.43% | 650 | 66.77% | 14.77% |
| LTC | 733 | 51.43% | 27.56% | 699 | 66.81% | 14.59% |

## BTC

Source: Binance BTCUSDT 1h candles rebuilt into UTC daily candles
Range: 2017-08-18 to 2026-06-24
Complete daily candles: 3204

### Bullish Sweep Reclaim

Target 1 = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 742 | 100.0% |
| Target hit anytime Day3 | 401 | 54.04% |
| Target before opposing | 378 | 50.94% |
| Opposing before target | 194 | 26.15% |
| 50% Day3 range before T1 | 282 | 38.01% |
| Consolidated inside Day2 range | 169 | 22.78% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 339 | 45.69% |
| target_first | 39 | 5.26% |
| opposing_first | 22 | 2.96% |
| opposing_only | 172 | 23.18% |
| same_hour_ambiguous | 1 | 0.13% |
| neither | 169 | 22.78% |

### Bullish Displacement

Target = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 771 | 100.0% |
| Target hit anytime Day3 | 507 | 65.76% |
| Target before opposing | 496 | 64.33% |
| Opposing before target | 103 | 13.36% |
| 50% Day3 range before T1 | 297 | 38.52% |
| Consolidated inside Day2 range | 172 | 22.31% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 446 | 57.85% |
| target_first | 50 | 6.49% |
| opposing_first | 11 | 1.43% |
| opposing_only | 92 | 11.93% |
| same_hour_ambiguous | 0 | 0.0% |
| neither | 172 | 22.31% |

## ETH

Source: Binance ETHUSDT 1h candles rebuilt into UTC daily candles
Range: 2017-08-18 to 2026-06-24
Complete daily candles: 3204

### Bullish Sweep Reclaim

Target 1 = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 715 | 100.0% |
| Target hit anytime Day3 | 381 | 53.29% |
| Target before opposing | 362 | 50.63% |
| Opposing before target | 192 | 26.85% |
| 50% Day3 range before T1 | 270 | 37.76% |
| Consolidated inside Day2 range | 159 | 22.24% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 332 | 46.43% |
| target_first | 30 | 4.2% |
| opposing_first | 17 | 2.38% |
| opposing_only | 175 | 24.48% |
| same_hour_ambiguous | 2 | 0.28% |
| neither | 159 | 22.24% |

### Bullish Displacement

Target = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 743 | 100.0% |
| Target hit anytime Day3 | 482 | 64.87% |
| Target before opposing | 474 | 63.8% |
| Opposing before target | 112 | 15.07% |
| 50% Day3 range before T1 | 261 | 35.13% |
| Consolidated inside Day2 range | 156 | 21.0% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 431 | 58.01% |
| target_first | 43 | 5.79% |
| opposing_first | 7 | 0.94% |
| opposing_only | 105 | 14.13% |
| same_hour_ambiguous | 1 | 0.13% |
| neither | 156 | 21.0% |

## ADA

Source: Binance ADAUSDT 1h candles rebuilt into UTC daily candles
Range: 2018-04-18 to 2026-06-24
Complete daily candles: 2965

### Bullish Sweep Reclaim

Target 1 = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 672 | 100.0% |
| Target hit anytime Day3 | 367 | 54.61% |
| Target before opposing | 353 | 52.53% |
| Opposing before target | 187 | 27.83% |
| 50% Day3 range before T1 | 224 | 33.33% |
| Consolidated inside Day2 range | 132 | 19.64% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 322 | 47.92% |
| target_first | 31 | 4.61% |
| opposing_first | 14 | 2.08% |
| opposing_only | 173 | 25.74% |
| same_hour_ambiguous | 0 | 0.0% |
| neither | 132 | 19.64% |

### Bullish Displacement

Target = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 627 | 100.0% |
| Target hit anytime Day3 | 416 | 66.35% |
| Target before opposing | 411 | 65.55% |
| Opposing before target | 86 | 13.72% |
| 50% Day3 range before T1 | 202 | 32.22% |
| Consolidated inside Day2 range | 130 | 20.73% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 380 | 60.61% |
| target_first | 31 | 4.94% |
| opposing_first | 5 | 0.8% |
| opposing_only | 81 | 12.92% |
| same_hour_ambiguous | 0 | 0.0% |
| neither | 130 | 20.73% |

## LINK

Source: Binance LINKUSDT 1h candles rebuilt into UTC daily candles
Range: 2019-01-17 to 2026-06-24
Complete daily candles: 2696

### Bullish Sweep Reclaim

Target 1 = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 573 | 100.0% |
| Target hit anytime Day3 | 322 | 56.2% |
| Target before opposing | 313 | 54.62% |
| Opposing before target | 140 | 24.43% |
| 50% Day3 range before T1 | 202 | 35.25% |
| Consolidated inside Day2 range | 120 | 20.94% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 281 | 49.04% |
| target_first | 32 | 5.58% |
| opposing_first | 9 | 1.57% |
| opposing_only | 131 | 22.86% |
| same_hour_ambiguous | 0 | 0.0% |
| neither | 120 | 20.94% |

### Bullish Displacement

Target = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 650 | 100.0% |
| Target hit anytime Day3 | 445 | 68.46% |
| Target before opposing | 434 | 66.77% |
| Opposing before target | 96 | 14.77% |
| 50% Day3 range before T1 | 229 | 35.23% |
| Consolidated inside Day2 range | 120 | 18.46% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 399 | 61.38% |
| target_first | 35 | 5.38% |
| opposing_first | 11 | 1.69% |
| opposing_only | 85 | 13.08% |
| same_hour_ambiguous | 0 | 0.0% |
| neither | 120 | 18.46% |

## LTC

Source: Binance LTCUSDT 1h candles rebuilt into UTC daily candles
Range: 2017-12-14 to 2026-06-24
Complete daily candles: 3087

### Bullish Sweep Reclaim

Target 1 = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 733 | 100.0% |
| Target hit anytime Day3 | 395 | 53.89% |
| Target before opposing | 377 | 51.43% |
| Opposing before target | 202 | 27.56% |
| 50% Day3 range before T1 | 264 | 36.02% |
| Consolidated inside Day2 range | 153 | 20.87% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 337 | 45.98% |
| target_first | 40 | 5.46% |
| opposing_first | 17 | 2.32% |
| opposing_only | 185 | 25.24% |
| same_hour_ambiguous | 1 | 0.14% |
| neither | 153 | 20.87% |

### Bullish Displacement

Target = Day2 high. Opposing side = Day2 low.

| Metric | Count | % |
|---|---:|---:|
| Events | 699 | 100.0% |
| Target hit anytime Day3 | 475 | 67.95% |
| Target before opposing | 467 | 66.81% |
| Opposing before target | 102 | 14.59% |
| 50% Day3 range before T1 | 257 | 36.77% |
| Consolidated inside Day2 range | 130 | 18.6% |

Sequence:

| Outcome | Count | % |
|---|---:|---:|
| target_only | 403 | 57.65% |
| target_first | 64 | 9.16% |
| opposing_first | 8 | 1.14% |
| opposing_only | 94 | 13.45% |
| same_hour_ambiguous | 0 | 0.0% |
| neither | 130 | 18.6% |
