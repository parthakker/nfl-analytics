# Model Report (v2)

Fitted 2026-08-29 02:21. Shipped configuration: **ewma ratings + QB flag** —
opponent-adjusted EPA ratings via EWMA (half-life **8** games, season carryover **0.6**) -> logistic win prob + ridge margin + causal QB-availability flag (expected starter Out/Doubtful/reserve).
Walk-forward by season; hyperparams tuned on 2012-2018 only; **2019-2024 is
the untouched holdout**; 2025 reported as bonus. Causality asserts cover every
input: EWMA ratings, ridge ratings, and QB flags are recomputed on truncated
history and diffed.

## Configuration comparison (one holdout evaluation each)

| config                                  |   tune_logloss |   holdout_brier |   holdout_margin_mae |   vs_market_gap | ship   |
|:----------------------------------------|---------------:|----------------:|---------------------:|----------------:|:-------|
| EWMA baseline (h=8, c=0.6)              |         0.6302 |          0.2239 |              10.2552 |          0.0134 | no     |
| Ridge (h=9, a=3, c=0.5)                 |         0.6303 |          0.2237 |              10.2441 |          0.0133 | no     |
| ewma + QB flag                          |         0.6304 |          0.2226 |              10.2401 |          0.0121 | SHIP   |
| ewma ratings + QB flag + drift controls |         0.6292 |          0.2223 |              10.2189 |          0.0118 | no     |

Gates: step 1 ships ridge only if holdout Brier <= 0.2224 AND margin MAE
is not worse than the EWMA baseline (failed). Step 2 ships the
QB flag only if it improves holdout Brier by >= 0.0010 over the step-1
result (passed). Only the gated-in configuration is persisted.

On the 95 holdout games where d_qb_out != 0, Brier is 0.1981 with
the flag vs 0.2219 without.

## Holdout 2019-2024 (1670 games, 1670 with moneylines)

| Metric | Model | Market (devigged ML) | Home-always |
|---|---|---|---|
| Brier | 0.2226 | 0.2105 | 0.2486 |
| Log loss | 0.6357 | 0.6085 | — |
| Margin MAE | 10.24 | 9.86 (closing spread) | — |

**Verdict:** the market is better than this model, as expected. Holdout Brier: market 0.2105 vs model 0.2226. Treat the model as a calibrated yardstick, not an oracle: a Kalshi price is interesting only when it disagrees with the model by MORE than the model's typical error vs the market, and after fees/spread.

## Calibration (holdout)

|   bin |       n |   predicted |   actual |    gap |
|------:|--------:|------------:|---------:|-------:|
| 0.000 |   1.000 |       0.069 |    0.000 | -0.069 |
| 1.000 |  12.000 |       0.170 |    0.583 |  0.413 |
| 2.000 |  73.000 |       0.262 |    0.247 | -0.015 |
| 3.000 | 148.000 |       0.353 |    0.304 | -0.049 |
| 4.000 | 294.000 |       0.453 |    0.381 | -0.073 |
| 5.000 | 392.000 |       0.551 |    0.485 | -0.066 |
| 6.000 | 387.000 |       0.649 |    0.628 | -0.021 |
| 7.000 | 248.000 |       0.743 |    0.738 | -0.005 |
| 8.000 | 109.000 |       0.837 |    0.853 |  0.016 |
| 9.000 |   6.000 |       0.921 |    1.000 |  0.079 |

Sample-weighted |gap| across the crowded middle of the range (0.35-0.70):
**0.0513**. Mean predicted home win probability
0.5718 against an actual home win rate of
0.5371.

## Drift controls (step 3): diagnosed, NOT shipped

The win model is refit on every season back to 1999 before each target
season, so its intercept carries a home-field advantage the league has partly
lost: home teams won ~57% of games through 2018, then 50-52% across 2019-2021
before recovering. That lag is the home-lean visible in the table above.

Two controls were tried against it — exponential recency weights on the
training rows, and a Platt layer fit on the previous N seasons of
walk-forward predictions (those predictions are already out-of-sample, so the
layer adds no leakage). Tuned on 2012-2018, best setting
recency_half_life=6.0, calibration_window=6:

| config                        |   holdout_brier |   calibration_gap |   mean_predicted |   2025_brier |
|:------------------------------|----------------:|------------------:|-----------------:|-------------:|
| ewma ratings + QB flag        |          0.2226 |            0.0513 |           0.5718 |       0.2295 |
| + recency=6.0, platt_window=6 |          0.2223 |            0.0150 |           0.5469 |       0.2301 |

The controls do what they were built to do — the mid-range calibration gap
falls from 0.0513 to 0.0150, and mean predicted home probability moves from
0.5718 to 0.5469 against 0.5371 actual — but they did NOT clear the step-3
Brier gate of 0.0010. A monotone recalibration cannot change which side the
model picks, so the ATS records are identical and Brier, dominated by
discrimination, barely moves.

Two caveats worth keeping in view. The tune window (2012-2018) is a stable-
home-field regime, so it cannot see the benefit of adapting — the whole grid
lands within 0.001 log loss there, which makes the tuned setting close to
arbitrary. And on 2025, the cleanest untouched season, the calibration gap
went 0.0546 -> 0.0889 and Brier 0.2295 -> 0.2301: the correction helps where
it was fitted and hurts where it was not, which is what lagging a regime
change looks like.

The code stays reachable via `recency_half_life` / `calibration_window` on
`backtest.walk_forward`. Shipping it would also need the Platt coefficients
persisted to `model_params` and applied in `predict.py`; train_model.py
refuses to ship without that plumbing.

## ATS vs closing spread (holdout, by disagreement threshold)

|   threshold |   bets |   wins |   win_pct |   breakeven | profitable   |
|------------:|-------:|-------:|----------:|------------:|:-------------|
|         0.5 |   1403 |    721 |    0.5139 |       0.524 | False        |
|         1   |   1192 |    603 |    0.5059 |       0.524 | False        |
|         2   |    802 |    406 |    0.5062 |       0.524 | False        |
|         3   |    529 |    275 |    0.5198 |       0.524 | False        |

Weeks 4+ only (early-season ratings are noisy):

|   threshold |   bets |   wins |   win_pct |   breakeven | profitable   |
|------------:|-------:|-------:|----------:|------------:|:-------------|
|         0.5 |   1163 |    606 |    0.5211 |       0.524 | False        |
|         1   |    992 |    506 |    0.5101 |       0.524 | False        |
|         2   |    662 |    341 |    0.5151 |       0.524 | False        |
|         3   |    431 |    226 |    0.5244 |       0.524 | True         |

## 2025 out-of-sample (never touched during tuning)

Brier 0.2295 vs market 0.2109
(284 games). Margin MAE 10.30 vs spread
9.68.

## Tuning grid — EWMA (2012-2018 walk-forward log loss)

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

## Tuning grid — decayed ridge (2012-2018 walk-forward log loss)

|   half_life |    alpha |   carryover |   logloss |
|------------:|---------:|------------:|----------:|
|     6.00000 |  3.00000 |     0.50000 |   0.63071 |
|     6.00000 |  3.00000 |     0.70000 |   0.63083 |
|     6.00000 |  3.00000 |     0.90000 |   0.63145 |
|     6.00000 | 10.00000 |     0.50000 |   0.63300 |
|     6.00000 | 10.00000 |     0.70000 |   0.63283 |
|     6.00000 | 10.00000 |     0.90000 |   0.63333 |
|     6.00000 | 30.00000 |     0.50000 |   0.64496 |
|     6.00000 | 30.00000 |     0.70000 |   0.64369 |
|     6.00000 | 30.00000 |     0.90000 |   0.64300 |
|     9.00000 |  3.00000 |     0.50000 |   0.63030 |
|     9.00000 |  3.00000 |     0.70000 |   0.63125 |
|     9.00000 |  3.00000 |     0.90000 |   0.63274 |
|     9.00000 | 10.00000 |     0.50000 |   0.63173 |
|     9.00000 | 10.00000 |     0.70000 |   0.63236 |
|     9.00000 | 10.00000 |     0.90000 |   0.63365 |
|     9.00000 | 30.00000 |     0.50000 |   0.64123 |
|     9.00000 | 30.00000 |     0.70000 |   0.64026 |
|     9.00000 | 30.00000 |     0.90000 |   0.64015 |
|    12.00000 |  3.00000 |     0.50000 |   0.63074 |
|    12.00000 |  3.00000 |     0.70000 |   0.63245 |
|    12.00000 |  3.00000 |     0.90000 |   0.63481 |
|    12.00000 | 10.00000 |     0.50000 |   0.63171 |
|    12.00000 | 10.00000 |     0.70000 |   0.63308 |
|    12.00000 | 10.00000 |     0.90000 |   0.63524 |
|    12.00000 | 30.00000 |     0.50000 |   0.63964 |
|    12.00000 | 30.00000 |     0.70000 |   0.63918 |
|    12.00000 | 30.00000 |     0.90000 |   0.63983 |
