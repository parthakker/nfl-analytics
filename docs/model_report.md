# Baseline Model Report

Fitted 2026-08-07 23:50. EWMA opponent-adjusted EPA ratings
(half-life **8** games, season carryover **0.6**) -> logistic win
prob + ridge margin. Walk-forward by season; hyperparams tuned on 2012-2018
only; **2019-2024 is the untouched holdout**; 2025 reported as bonus.

## Holdout 2019-2024 (1670 games, 1670 with moneylines)

| Metric | Model | Market (devigged ML) | Home-always |
|---|---|---|---|
| Brier | 0.2239 | 0.2105 | 0.2486 |
| Log loss | 0.6382 | 0.6085 | — |
| Margin MAE | 10.26 | 9.86 (closing spread) | — |

**Verdict:** the market is better than this model, as expected. Holdout Brier: market 0.2105 vs model 0.2239. Treat the model as a calibrated yardstick, not an oracle: a Kalshi price is interesting only when it disagrees with the model by MORE than the model's typical error vs the market, and after fees/spread.

## Calibration (holdout)

|   bin |       n |   predicted |   actual |    gap |
|------:|--------:|------------:|---------:|-------:|
| 1.000 |  12.000 |       0.163 |    0.417 |  0.254 |
| 2.000 |  66.000 |       0.260 |    0.288 |  0.028 |
| 3.000 | 153.000 |       0.353 |    0.301 | -0.053 |
| 4.000 | 296.000 |       0.454 |    0.389 | -0.065 |
| 5.000 | 391.000 |       0.550 |    0.486 | -0.064 |
| 6.000 | 385.000 |       0.647 |    0.618 | -0.029 |
| 7.000 | 256.000 |       0.742 |    0.738 | -0.004 |
| 8.000 | 106.000 |       0.836 |    0.849 |  0.013 |
| 9.000 |   5.000 |       0.918 |    1.000 |  0.082 |

## ATS vs closing spread (holdout, by disagreement threshold)

|   threshold |   bets |   wins |   win_pct |   breakeven | profitable   |
|------------:|-------:|-------:|----------:|------------:|:-------------|
|         0.5 |   1407 |    721 |    0.5124 |       0.524 | False        |
|         1   |   1199 |    612 |    0.5104 |       0.524 | False        |
|         2   |    826 |    417 |    0.5048 |       0.524 | False        |
|         3   |    539 |    276 |    0.5121 |       0.524 | False        |

Weeks 4+ only (early-season ratings are noisy):

|   threshold |   bets |   wins |   win_pct |   breakeven | profitable   |
|------------:|-------:|-------:|----------:|------------:|:-------------|
|         0.5 |   1165 |    605 |    0.5193 |       0.524 | False        |
|         1   |    996 |    514 |    0.5161 |       0.524 | False        |
|         2   |    682 |    351 |    0.5147 |       0.524 | False        |
|         3   |    441 |    228 |    0.517  |       0.524 | False        |

## 2025 out-of-sample (never touched during tuning)

Brier 0.2278 vs market 0.2109
(284 games). Margin MAE 10.28 vs spread
9.68.

## Tuning grid (2012-2018 walk-forward log loss)

|   half_life |   carryover |   logloss |
|------------:|------------:|----------:|
|     6.00000 |     0.40000 |   0.63164 |
|     6.00000 |     0.50000 |   0.63100 |
|     6.00000 |     0.60000 |   0.63075 |
|     8.00000 |     0.40000 |   0.63097 |
|     8.00000 |     0.50000 |   0.63033 |
|     8.00000 |     0.60000 |   0.63020 |
|    10.00000 |     0.40000 |   0.63101 |
|    10.00000 |     0.50000 |   0.63046 |
|    10.00000 |     0.60000 |   0.63046 |
|    12.00000 |     0.40000 |   0.63137 |
|    12.00000 |     0.50000 |   0.63091 |
|    12.00000 |     0.60000 |   0.63105 |
