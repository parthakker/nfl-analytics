# Baseline Model Report

Fitted 2026-08-02 16:43. EWMA opponent-adjusted EPA ratings
(half-life **8** games, season carryover **0.6**) -> logistic win
prob + ridge margin. Walk-forward by season; hyperparams tuned on 2012-2018
only; **2019-2024 is the untouched holdout**; 2025 reported as bonus.

## Holdout 2019-2024 (1670 games, 1670 with moneylines)

| Metric | Model | Market (devigged ML) | Home-always |
|---|---|---|---|
| Brier | 0.2237 | 0.2105 | 0.2486 |
| Log loss | 0.6378 | 0.6085 | — |
| Margin MAE | 10.24 | 9.86 (closing spread) | — |

**Verdict:** the market is better than this model, as expected. Holdout Brier: market 0.2105 vs model 0.2237. Treat the model as a calibrated yardstick, not an oracle: a Kalshi price is interesting only when it disagrees with the model by MORE than the model's typical error vs the market, and after fees/spread.

## Calibration (holdout)

|   bin |       n |   predicted |   actual |    gap |
|------:|--------:|------------:|---------:|-------:|
| 0.000 |   1.000 |       0.097 |    0.000 | -0.097 |
| 1.000 |  13.000 |       0.161 |    0.385 |  0.223 |
| 2.000 |  76.000 |       0.257 |    0.263 |  0.006 |
| 3.000 | 166.000 |       0.353 |    0.295 | -0.058 |
| 4.000 | 296.000 |       0.453 |    0.402 | -0.051 |
| 5.000 | 381.000 |       0.551 |    0.512 | -0.039 |
| 6.000 | 376.000 |       0.648 |    0.606 | -0.041 |
| 7.000 | 240.000 |       0.742 |    0.742 | -0.001 |
| 8.000 | 114.000 |       0.834 |    0.851 |  0.017 |
| 9.000 |   7.000 |       0.917 |    0.857 | -0.060 |

## ATS vs closing spread (holdout, by disagreement threshold)

|   threshold |   bets |   wins |   win_pct |   breakeven | profitable   |
|------------:|-------:|-------:|----------:|------------:|:-------------|
|         0.5 |   1419 |    727 |    0.5123 |       0.524 | False        |
|         1   |   1189 |    608 |    0.5114 |       0.524 | False        |
|         2   |    818 |    418 |    0.511  |       0.524 | False        |
|         3   |    523 |    269 |    0.5143 |       0.524 | False        |

Weeks 4+ only (early-season ratings are noisy):

|   threshold |   bets |   wins |   win_pct |   breakeven | profitable   |
|------------:|-------:|-------:|----------:|------------:|:-------------|
|         0.5 |   1175 |    611 |    0.52   |       0.524 | False        |
|         1   |    988 |    513 |    0.5192 |       0.524 | False        |
|         2   |    671 |    347 |    0.5171 |       0.524 | False        |
|         3   |    429 |    219 |    0.5105 |       0.524 | False        |

## 2025 out-of-sample (never touched during tuning)

Brier 0.2285 vs market 0.2109
(284 games). Margin MAE 10.30 vs spread
9.68.

## Tuning grid (2012-2018 walk-forward log loss)

|   half_life |   carryover |   logloss |
|------------:|------------:|----------:|
|     6.00000 |     0.40000 |   0.63226 |
|     6.00000 |     0.50000 |   0.63156 |
|     6.00000 |     0.60000 |   0.63128 |
|     8.00000 |     0.40000 |   0.63200 |
|     8.00000 |     0.50000 |   0.63128 |
|     8.00000 |     0.60000 |   0.63104 |
|    10.00000 |     0.40000 |   0.63256 |
|    10.00000 |     0.50000 |   0.63179 |
|    10.00000 |     0.60000 |   0.63160 |
|    12.00000 |     0.40000 |   0.63344 |
|    12.00000 |     0.50000 |   0.63264 |
|    12.00000 |     0.60000 |   0.63249 |
