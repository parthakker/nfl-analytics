# The Betting Primer

A betting line is a price, and everything in this chapter follows from taking that literally. Markets on NFL games are crowdsourced win-probability estimates with a toll booth attached, and betting them well is less about picking winners than about finding prices that are wrong — then proving it over a sample large enough to mean something. This chapter covers the mechanics (spreads, totals, moneylines, American odds), the math (implied probability, vig, devigging — with worked examples), the concepts that separate sharp process from square results (key numbers, line movement, CLV), and how prediction markets like Kalshi map onto all of it. The app's [/betting](/betting) page applies these ideas live, scanning for dislocations between Kalshi prices and the Vegas lines tracked in the warehouse.

## The three basic markets

**The spread** is a handicap that makes both teams equally attractive. Chiefs −3.5 means the Chiefs must win by 4+ for their backers to cash; Broncos +3.5 cashes on any Broncos result including a 3-point loss. The spread is *not* a prediction of the median margin so much as the price that balances informed money on both sides — usually close to the same thing, not always. A positive home spread in this warehouse's `schedules` convention means the home team is favored; the derived team-game view flips it to always mean "this team favored by."

**The total** (over/under) prices combined points: Over 47.5 needs 48+. Totals are where weather, pace, and referee tendencies (see [/refs](/refs)) live.

**The moneyline** is a straight bet on the winner, priced by odds instead of a handicap: a −3.5 favorite might be −180 on the moneyline, the underdog +155. Spread and moneyline are two views of the same distribution, and their consistency with each other is itself information.

Standard spread/total bets carry −110 pricing: risk $110 to win $100. That 10 is the toll booth.

## American odds, decoded

American odds answer one of two questions. **Negative odds**: how much must I risk to win $100? **Positive odds**: how much do I win if I risk $100?

Implied probability formulas:

- Negative odds: |odds| ÷ (|odds| + 100)
- Positive odds: 100 ÷ (odds + 100)

| American | Risk → win | Implied probability | Decimal odds |
|---|---|---|---|
| −300 | $300 → $100 | 75.0% | 1.33 |
| −200 | $200 → $100 | 66.7% | 1.50 |
| −150 | $150 → $100 | 60.0% | 1.67 |
| −120 | $120 → $100 | 54.5% | 1.83 |
| −110 | $110 → $100 | 52.4% | 1.91 |
| +100 (even) | $100 → $100 | 50.0% | 2.00 |
| +120 | $100 → $120 | 45.5% | 2.20 |
| +150 | $100 → $150 | 40.0% | 2.50 |
| +200 | $100 → $200 | 33.3% | 3.00 |
| +300 | $100 → $300 | 25.0% | 4.00 |

The number to memorize: **−110 implies 52.38%** (110 ÷ 210). That's the break-even win rate for standard spread bets. Win 52.4% of your −110 bets forever and you exactly tread water; the celebrated sharp who hits 55% long-term is clearing about 5 cents of edge per dollar. Anyone claiming 65% against the spread over a real sample is describing a fantasy.

## Vig, and how to remove it

Add up the implied probabilities of both sides of any market and you'll get more than 100%. That excess — the **overround** — is the book's margin, the **vig**. At −110/−110: 52.38% + 52.38% = **104.76%**. The extra 4.76 points is the toll; as a fraction of total handle the book's expected hold is 4.76 ÷ 104.76 ≈ **4.5%**.

**Devigging** removes the toll to recover the market's true opinion. The simplest method (multiplicative) just rescales each side to sum to 100%. Worked example — a moneyline market at **−150 / +130**:

1. Favorite implied: 150 ÷ 250 = **60.00%**
2. Underdog implied: 100 ÷ 230 = **43.48%**
3. Overround: 60.00 + 43.48 = **103.48%**
4. Devigged favorite: 60.00 ÷ 103.48 = **57.98%**
5. Devigged underdog: 43.48 ÷ 103.48 = **42.02%**

Check: 57.98 + 42.02 = 100. The market's actual opinion is that the favorite wins about **58%** of the time — not 60%. This matters constantly: comparing your model (or a Kalshi price) to the *raw* implied probability of one side systematically flatters the book. Always devig first. (Fancier methods — power devig, shin — handle favorite-longshot bias better on lopsided markets; multiplicative is fine for game lines.)

## Key numbers: why 3 and 7 are sacred

Football scores cluster, because scoring comes in 3s and 7s. The most common final margin in NFL history is exactly **3**, historically landing in the neighborhood of 15% of games (one in seven), with **7** next around 9%, and 10, 6, and 4 in the following tier. Consequences:

- **The gap between −2.5 and −3.5 is enormous** — it spans the single biggest pile of outcomes. The gap between −7.5 and −8.5 is trivial by comparison.
- **Half-point pricing reflects it.** Books charge extra to buy on/off 3 (moving −3 to −2.5 costs well more than the standard 10 cents) precisely because that half point is worth real win probability.
- **Line shopping is worth most at key numbers.** Having +3 at one book when others show +2.5 is a genuine, quantifiable edge; grinding for +9.5 vs +9 is hobby-tier.
- **Middles live here**: catch a game at −2.5 and +3.5 and a 3-point favorite win cashes both.

Totals have soft key numbers too (37, 41, 44, 47, 51 — combinations of 3s and 7s), but they're far weaker than spread keys.

## Line movement and CLV

Lines open, money arrives, lines move. The closing line — kickoff's final price — is the market's most informed estimate, sharpened by everything learned during the week: injuries, weather, and the opinions of the bettors books respect.

**Closing line value (CLV)** is the practice of grading yourself against the close instead of the result. Bet Chiefs −2.5 on Tuesday; the line closes −3.5; you beat the close by a point through the market's biggest key number — a clearly good bet *regardless of Sunday's outcome*. The empirical foundation of sharp betting is that consistently beating the closing line predicts long-term profit far better than short-term win-loss does, because results are noisy (a season is ~280 games; one bettor's card might be 80 bets, where a 55% true talent goes 36–44 with unremarkable frequency) while CLV measures the thing you control: getting better prices than the market's final opinion. The warehouse's `line_snapshots` table exists for exactly this — Vegas line history appended at every refresh, so opening-to-closing moves are queryable after the fact.

Related vocabulary: **steam** (sharp-driven synchronized movement across books), **reverse line movement** (line moves against the majority of tickets — a sharp-money tell), and **ATS records** (against the spread). Treat ATS records with suspicion at small samples: "7–2 ATS in their last nine" is 9 coin flips with a story attached, and situational ATS trends ("NFC dogs off a bye in October") are mostly survivorship mining. An ATS record becomes interesting when it's large-sample and attached to a mechanism — which is how the coach ATS numbers in this app's coach pages are meant to be read.

## Parlays and teasers

A **parlay** chains bets; every leg must win. For independent legs, multiply decimal odds: two −110 legs → 1.909 × 1.909 = 3.645, so a true-odds two-teamer pays +264 (books historically paid 2.6/1, near-fair; longer parlays get progressively worse). Parlays don't manufacture edge — they compound whatever edge (or vig) the legs carry. Negative-EV legs get *more* negative in parlays; positive-EV legs compound beautifully, which is why books limit sharp parlay bettors. **Correlated parlays** are the exception worth understanding: when legs move together (a huge favorite covering + the game going under; a QB's passing yards + his top receiver's), the true joint probability exceeds the naive product, and if the book prices legs independently, the parlay is mispriced in your favor. Books ban or reprice the obvious correlations (same-game parlays are priced on joint models), but correlation hunting remains one of the few structural edges left in retail books.

A **teaser** buys points on multiple legs at the cost of a shorter payout — classically 6 points, two teams, around −120 to −130. The break-even math: at −120 you need the combined 54.55%, so each leg must hit √0.5455 ≈ **73.9%**. The **Wong teaser** insight: 6-point teases that cross *both* 3 and 7 (favorites −7.5 to −8.5 teased down through both keys, underdogs +1.5 to +2.5 teased up through them) historically converted at rates near or above that threshold. Books have since shaded teaser pricing to −130/−135 in response — the edge is thinner than the blog era, but the principle (tease *through* key numbers or don't tease) stands.

## Prediction markets: Kalshi mechanics

Kalshi is a regulated exchange for event contracts, and its NFL markets (game winners, spreads, totals, season wins, Super Bowl — the series this app snapshots every six hours) work like binary options:

- Every contract resolves to **$1 (Yes) or $0 (No)**. Prices are quoted in cents, 1–99¢.
- **Price ≈ implied probability.** A Yes at 62¢ implies ~62%. Buy at 62¢ and resolution Yes pays $1 — 38¢ profit per contract.
- You're trading against **other participants on an order book**, not a bookmaker. There's no vig baked into the price itself; instead there's a **bid-ask spread** plus **trading fees**, which are proportional to price × (1 − price) — maximal near 50¢ (roughly 1.75¢ per contract at 50¢ under the standard 7% formula), shrinking toward the extremes.
- You can **sell before resolution** — Kalshi positions are tradeable, so CLV isn't just a grading tool, it's realizable profit. Buy at 40¢, sell at 55¢, never sweat the game.

Mapping to Vegas is where it gets useful. Worked example: Vegas has a favorite at −150 / +130, which devigs (from earlier) to **58.0%**. Kalshi's Yes on that favorite is asking **62¢**. That's a four-point dislocation: the Kalshi Yes is *overpriced* relative to the sharpest available estimate, and the value — if you trust the Vegas devig — is buying **No around 38–39¢** against a fair value of 42%. After fees and spread, call it a ~3-point edge; on a binary contract that's substantial. The reverse happens too, especially in thin markets, on news lags, and in longshot territory where retail flow distorts prices.

This is precisely what [/betting](/betting) does: line up devigged Vegas probabilities against Kalshi's order book, market by market, and surface the dislocations. Two honest caveats it operates under. Liquidity: Kalshi NFL books can be thin outside marquee games, and a 4-point edge you can only get $50 down on is a curiosity. And "Vegas is right" is an assumption — a good one at close, weaker on Tuesday. Market-vs-market comparison finds *relative* mispricing; it can't tell you which side of the disagreement is wrong.

## The discipline layer

The math above is necessary, not sufficient. The rest is bankroll and record-keeping: flat-stake or fractional-Kelly sizing (full Kelly overbets any realistic estimate error), one to three percent of bankroll per play, and a written record of every bet with its closing line — because CLV, not your win-loss record, is the earliest honest signal of whether any of this is working. Track everything; the sample will tell you the truth eventually, and the whole point of doing this with a warehouse underneath you is that you never have to argue with the sample.
