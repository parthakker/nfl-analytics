# How the Jarvis Model Works

Jarvis carries one prediction model. It is small on purpose — eight inputs, two linear equations, no black box — because the point of it is not to beat Las Vegas (it doesn't, and the chapter is honest about that) but to be a *yardstick* you fully understand: a number to hold up against a market price, and a sandbox for learning how prediction models are built and judged. This chapter is the model's owner's manual. Every number in it comes from the model's own report card on the **Model Lab** page (More → Model), and the last section shows how to run your own experiment in a few seconds.

## What it predicts

For any matchup the model produces two numbers, both from the home team's point of view:

- **Home win probability** — a number between 0 and 1. The model's opinion that the home team wins.
- **Predicted margin** — home points minus away points. Positive means home by that many; it lines up with the spread the same way (a `−3.5` spread means the home team is favoured by 3.5).

It predicts nothing else. No totals, no player props, no quarter-by-quarter. That is deliberate: one target, done carefully, is worth more than five done loosely, and the totals model is the obvious next thing to build with the tools below.

## The eight inputs, in plain English

Everything the model knows about a game is eight numbers. Four are **team-strength differences**, four are **game context**. Every input is defined so that *positive helps the home team*, which makes the coefficients readable.

### The four rating differences

Each team carries four ratings, all in **EPA per play relative to league average** (see [The Analytics Primer](/knowledge/analytics-primer) for EPA): passing offense, rushing offense, passing defense, rushing defense. Offense ratings are EPA gained; defense ratings are EPA *allowed*, so for defense **lower is better**.

The ratings are built game by game as an **exponentially weighted moving average (EWMA)** of each team's opponent-adjusted performance:

- **Opponent-adjusted** means a team's pass-offense EPA in a game is credited against the *defense it faced* — +0.10 EPA/play against a top-3 pass defense counts for more than +0.10 against the worst. Each side's adjustment uses the opponent's rating *entering* that game, never after, so no result ever influences its own inputs.
- **Half-life = 8 games** is the memory setting. A game eight games ago counts half as much as the most recent one; sixteen games ago, a quarter. Shorter half-lives react faster to a hot streak but are noisier; longer ones are steadier but slow to notice a team has changed. Eight was chosen by testing 6, 8, 10 and 12 on the 2012–2018 seasons.
- **Carryover = 0.6** is what survives the offseason. At the first game of a new season every rating is multiplied by 0.6 — shrunk 40% toward league average — because rosters, coaches and schemes change. This is why week 1–3 predictions are the shakiest: the ratings are mostly last year's, diluted.

The model does not see ratings directly. It sees the **difference**: home minus away for the two offense ratings, and **away minus home** for the two defense ratings. That second sign flip is the single most common bug in models like this — it exists because a lower defense number is *better*, so flipping it keeps "positive = good for home" true on all four columns. A unit test pins the training and serving code to the same arithmetic.

### The four context inputs

| Input | What it is | Why it might matter |
|---|---|---|
| **Rest edge** | Home rest days minus away rest days, each clipped to the 3–14 range (unknown = 7) | Short weeks and byes. The coefficient is small: about 0.2 points per day. |
| **Away time-zone shift** | Hours the away team travelled east (positive) or west (negative) | West-coast teams in 1 pm ET kickoffs are a betting-folklore staple; the model finds almost nothing. |
| **Division game** | 1 if the teams share a division | Familiarity compresses outcomes: worth roughly −0.7 points to the home side. |
| **QB availability** | Home QB-out flag minus away QB-out flag, where "out" means the *expected starter* is listed Out/Doubtful/reserve | The biggest single-input effect: a missing starting QB is worth about 3 points. "Expected starter" is derived only from the previous game's dropbacks, never from who actually played, so it cannot peek. |

## How it learns: two straight lines

The model is a **logistic regression** for the win probability and a **ridge regression** for the margin, both fitted on the same eight inputs. Each is one coefficient per input plus an intercept:

- margin = baseline + Σ (coefficient × input)
- win probability = 1 / (1 + e^−(baseline + Σ coefficient × input))

That is the whole model. The Model Lab's **Report card** tab lists every coefficient in points-per-unit, and the **This week** tab draws, for each game, exactly which inputs are pushing the margin which way. Because the equations are linear, those bars are an *exact* decomposition of the prediction, not an approximation.

The intercept is the **home-field baseline** — what the model expects with all eight inputs at zero. Right now it is about +2.5 points, and that number is the source of the model's best-known flaw (next section).

## How it is judged: walk-forward, and the holdout you never touch

A model that has seen a game's result can "predict" it perfectly, so the test has to simulate real life. Jarvis uses **walk-forward validation**: to predict the 2019 season, it fits on 1999–2018 only. For 2020, on 1999–2019. And so on. Every prediction in the record was made by a model that had never seen that season.

On top of that, the seasons are split into roles that are never mixed:

- **2012–2018 — the tuning window.** The only seasons ever used to *choose* settings (half-life, carryover, which inputs to include). Choosing by looking at any other seasons would be cheating.
- **2019–2024 — the holdout.** Six seasons, 1,670 games, that no setting was ever tuned on. The report card numbers are all from here. The rule is *one evaluation per candidate configuration*: the moment you start trying things until the holdout looks good, it stops being a holdout.
- **2025 — the bonus season.** Reported separately as the cleanest untouched year.

The training script also runs **causality checks**: it recomputes every input on history truncated at 2015 and verifies that nothing before 2015 changed. If later data could leak backward into earlier ratings, this fails loudly.

## Reading the report card

### Brier score — the headline number

For each game, take the predicted home win probability, subtract 1 if home won or 0 if they lost, and square it. Average that over all games. That is the **Brier score**. Lower is better, and it rewards two things at once: *discrimination* (saying 80% for teams that win 80% of the time) and *calibration* (not saying 80% when 60% is true).

Three reference points make it readable:

| Predictor | Holdout Brier (2019–2024) |
|---|---|
| Always predict the base home-win rate (~54%) | 0.2486 |
| **The Jarvis model** | **0.2226** |
| The devigged closing moneyline (the market) | 0.2105 |

A coin flip scores 0.25. The model is clearly better than a coin flip and clearly worse than the market — which is exactly what an eight-input public-data model should be. Sportsbooks price in injuries, weather, motivation, and the wisdom of everyone betting into them. Beating them with EPA ratings and rest days would be evidence of a bug, not brilliance.

The gap to the market — about 0.012 — is the number to watch when you change something. The ship gate in the training script is an improvement of **0.0010** in holdout Brier; anything smaller is inside the noise of a single six-season sample.

### Calibration — is 60% really 60%?

Group the holdout games by predicted probability (all the 60–70% predictions together, and so on) and compare the predicted rate with the actual home-win rate in each bucket. Perfectly calibrated predictions sit on the diagonal of the Report card's calibration chart.

The Jarvis model has a known lean: across the crowded middle of the range it is about **5 points too confident in the home team** — it predicts a 57% home win rate on the holdout while the actual rate is 54%. The cause is structural. The intercept is fitted on every season back to 1999, when home teams won about 57% of games; from 2019 the league's home-field advantage dropped to the low 50s and has only partly recovered. A model trained on 25 years of history lags a regime change.

Two fixes have been built and tested (recency weighting of training seasons, and a Platt recalibration layer fitted on earlier out-of-sample predictions). They cut the calibration gap from 0.051 to 0.015 — and moved Brier by only 0.0003, because a monotone correction can't change *which* team the model favours, and Brier is dominated by that. They stay switched off, reachable through `nfl experiment --recency 6 --calib-window 6`. Whether a calibration gate should sit alongside the Brier gate is an open design question worth having an opinion on.

### Margin error and ATS

The predicted margin misses by **10.2 points** on average; the closing spread misses by 9.9 on the same games. Betting the model against the spread whenever it disagrees by 3+ points has gone roughly 52% on the holdout — right at the 52.4% breakeven for −110 pricing, on a few hundred bets. That is not an edge; it is the definition of noise. The Betting pages stay market-vs-market for this reason.

## What the model is for

Not for picking winners against the book. It is for:

- **A second opinion with known error bars.** When a Kalshi price and the model disagree by *more* than the model's typical gap to the market, that is worth a look — after fees.
- **Seeing the reasoning.** The This-week bars show *why* a team is favoured in the model's eyes, in points, per input. That is a better teaching tool than any single probability.
- **A baseline to beat.** Every new idea — weather, a totals model, a better QB signal — gets measured against 0.2226 on the same holdout by the same script.

## Run your own experiment

The full training protocol (`nfl train`, ~2–5 minutes) tunes grids, applies the ship gates and overwrites the model tables. You do not need it to try an idea. `nfl experiment` runs **one** configuration through the full walk-forward in a few seconds, prints a scorecard against the shipped model and the market, and appends a line to the log the Model Lab's **Experiments** tab reads. Nothing is persisted to the warehouse.

```
nfl experiment --note "baseline"                          # reproduces the shipped 0.2226
nfl experiment --features -d_qb_out --note "no QB flag"   # drop an input
nfl experiment --half-life 12 --note "slower ratings"     # change a setting
nfl experiment --recency 6 --calib-window 6 --note "drift controls"
```

The scorecard reads like this:

```
  model            0.2226   0.6357  10.24
  market           0.2105   0.6085   9.86
  home-always      0.2486
  shipped          0.2226   -> this run is +0.0000 (same)
```

Three good first experiments, each of which teaches something:

1. **Drop the QB flag** (`--features -d_qb_out`). Brier should get worse by about 0.001 — the size of one shipped input. Notice how small "important" is.
2. **Half-life 4 vs 16.** Fast memory versus slow. Watch Brier *and* the 2025 bonus line: settings that win on the holdout and lose on the bonus season are a warning.
3. **Switch rest to the schedule's rest days.** The model currently trains on the lag-computed `rest_days`, which is unknown in week 1 (treated as 7). The warehouse also carries `rest_days_sched`, populated from week 1. Wiring it in (`features.py`, one line, then `--features +d_rest_sched,-d_rest`) is the first real modelling change to make — and it changes every training row, which is why it has not been done casually.

When something clears the gate, the path to shipping it is the training script: add it to the registry there, let the protocol gate it on the holdout once, and it becomes the new 0.2226.

---

*The tables behind this chapter: `model_params` (the coefficients), `model_ratings` (current team ratings), `model_predictions` (every walk-forward prediction 2012–2025), `model_rating_history` (each team's rating entering each game). The code: `src/nfl_analytics/model/`. The log: `logs/model_experiments.jsonl`.*
