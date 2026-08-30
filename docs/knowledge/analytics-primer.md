# The Analytics Primer

Box-score football stats were designed in the 1930s to fill newspaper columns, and they still mostly measure *what happened* without asking *what it was worth*. A 3-yard run on 3rd-and-2 and a 3-yard run on 3rd-and-9 are identical in the box score and opposites on the field. Modern NFL analytics is one long correction of that mistake: put every play in context — down, distance, field position, clock, score — and value it against expectation. This chapter builds the toolkit from the ground up: EPA, win probability, success rate, CPOE, PROE, the air-yards family, and the discipline of knowing when a number is signal and when it's a small-sample mirage. Nearly everything here is computable from this app's play-by-play warehouse, and several of the metrics are precomputed as views.

## Expected points: the foundation

Start with a question: how many points is a given game state worth? Specifically — for this down, distance, and field position, what's the average *net* points the offense will eventually get from here (counting the possibility that the ball changes hands)? Fit that from millions of historical plays and you get an **expected points (EP)** model.

Illustrative values in the spirit of public EP models (nflfastR's is the open-source standard, and its outputs are in this warehouse's play-by-play):

- 1st-and-10 at your own 25: roughly **+1** point
- 1st-and-10 at midfield: roughly **+2.5**
- 1st-and-goal at the 3: roughly **+6**
- 3rd-and-15 at your own 5: slightly **negative** — the most likely next score is the opponent's

**EPA (expected points added)** is just the change: EP after the play minus EP before it. Two worked examples with round numbers:

- 1st-and-10 at your own 25 (EP ≈ +1.0). An 8-yard completion makes it 2nd-and-2 at the 33 (EP ≈ +1.4). **EPA = 1.4 − 1.0 = +0.4.**
- Same start, incompletion: now 2nd-and-10 at the 25 (EP ≈ +0.6). **EPA = 0.6 − 1.0 = −0.4.**

Notice what happened: an 8-yard gain — a "successful play" in any box score — earned +0.4, while the incompletion cost about the same. EPA prices downs, not just yards. A 3-yard conversion on 3rd-and-2 is worth far more than a 5-yard gain on 3rd-and-9, because the first buys a fresh set of downs and the second buys a punt. Touchdowns resolve to roughly +7 minus the EP you already had — scoring from the 1-yard line adds little because you'd already banked most of it.

**EPA/play** is then the workhorse team and player metric: average EPA across a unit's plays. Offensive EPA/play separates good offenses from bad ones better than yards per game ever did, and QB EPA/play (including sacks and scrambles, which yards-per-attempt ignores) is the single best public one-number QB stat.

### The filters matter as much as the metric

EPA/play is only comparable if everyone computes it over the same plays. The conventions this app uses (and states in its answers):

- **Plays:** `play_type IN ('pass','run')` — real snaps only, no kneels, spikes, or penalties-no-play. Scrambles count as pass plays (they're outcomes of a called pass).
- **Season type:** regular season unless stated.
- **Garbage time:** blowout minutes contain fake production — prevent defenses concede short completions, trailing teams abandon the run. Common fixes are filtering by win probability (e.g., keep plays where WP is between 5% and 95%) or by score/quarter windows. There's no single right filter; there is a wrong move, which is not stating yours.
- **Down/distance/field-position splits:** early-down EPA (1st/2nd down) is the most predictive slice of offense, because 3rd downs are high-variance and teams that live on them regress.

## Win probability

Same idea as EP, different currency. A **win probability (WP)** model estimates the chance the team wins from the full game state — score, clock, timeouts, field position, down and distance. **WPA** (win probability added) is the per-play change.

EPA and WP serve different masters. EPA is *score-agnostic* — the right lens for "how good is this offense?" because maximizing points is the job in the aggregate. WP is *situation-obsessed* — the right lens for decisions: a field goal down 4 with two minutes left adds expected points and nearly zero win probability. Fourth-down bots run on WP. Player evaluation runs on EPA. Mixing them up produces takes like crediting a QB for garbage-time WPA heroics or blaming a coach for an EV-correct decision that failed.

WP is also the honest way to talk about single games: a team that was 90% to win and lost didn't get "exposed" — a one-in-ten event happened. Betting markets (see [The Betting Primer](/knowledge)) are, functionally, tradeable win-probability estimates.

## Success rate

EPA's stable sibling. A play is a **success** if its EPA is positive — in this warehouse, `success = epa > 0`, exactly. Success rate is the fraction of plays that succeed.

Why carry both? EPA is mean-driven and fat-tailed: one 75-yard touchdown can float a game's average. Success rate is a median-style measure — it asks *how often* you win the down, not by how much. An offense with high EPA but mediocre success rate is boom-or-bust (deep shots, breakaway runs); high success rate with modest EPA is a grinding, on-schedule offense. Success rate is also the better rushing metric, since rushing EPA is dominated by rare explosive runs. For stability across small samples, success rate > EPA; for capturing true impact, EPA > success rate. Read them together.

## CPOE: completion percentage over expected

Raw completion percentage is mostly a *style* stat — a QB throwing screens will complete 70% while a downfield thrower completes 62%, and the second may be far better. **CPOE** fixes this by modeling the expected completion probability of each throw (depth, direction, field position, down/distance — and in tracking-data versions like NGS, receiver separation and pressure) and crediting the QB with the difference.

Worked example: a QB's throws carry an average expected completion probability of 63%; he completes 68%. **CPOE = 68 − 63 = +5 percentage points** — elite territory. League leaders live in the +3 to +6 range; below −3 is a red flag no play-caller can scheme away. CPOE stabilizes faster than most QB stats and, blended with EPA/play (the popular composite weights EPA/play most heavily), gives the best quick read on QB quality. The warehouse carries CPOE per play (2016+, from the tracking-era models) and NGS completion-probability aggregates.

## PROE and expected pass rate

How often *should* a team pass? Model the league-average pass probability for every situation — down, distance, field position, clock, score differential — and you get **xpass**. A team's **PROE (pass rate over expected)** is its actual pass rate minus the expected rate over its plays.

This is the right way to talk about play-calling identity, because raw pass rate is contaminated by game script: bad teams trail, and trailing teams throw. A team can rank 10th in raw pass rate while being the most run-heavy team in football by choice. PROE strips the situation out: +5% PROE means this coach passes five points more than an average coach *would in his exact situations*. It's a coach fingerprint — stable across seasons, diagnostic of philosophy, and predictive of how an offense will behave in neutral situations. This app computes PROE per coach (along with 4th-down go rate and tempo, rbsdm-style) at [/coaches](/coaches), and the neutral-situation splits matter for both betting totals and fantasy volume projections.

## The air-yards family

Passing yards come in two parts: the ball's flight and the run after the catch. Separating them turns one stat into a family:

| Metric | Definition | What it tells you |
|---|---|---|
| Air yards | Distance from line of scrimmage to the catch point (or target spot), per throw | Downfield ambition |
| aDOT | Average depth of target | Role: 4 = checkdown outlet, 9 = intermediate, 14+ = deep threat |
| YAC | Yards after catch | Playmaking + scheme (screens inflate it) |
| RACR | Receiving yards ÷ air yards | Efficiency per air yard thrown at you |
| Target share | % of team targets | The volume king |
| Air-yards share | % of team air yards | Volume, weighted by depth |
| **WOPR** | 1.5 × target share + 0.7 × air-yards share | The blended opportunity score |

Two uses. For QBs, aDOT contextualizes everything (that 70% completion rate at 5.5 aDOT is a choice, not an achievement). For receivers, **air yards are earned** — a target 30 yards downfield reflects a coach's trust and a real opportunity, even incomplete — which is why WOPR (weighted opportunity rating, the 1.5/0.7 blend above) predicts future fantasy production better than past fantasy points do. Opportunity persists; touchdown luck doesn't. The [Fantasy Primer](/knowledge) builds on exactly this.

## Opponent adjustment: the DVOA idea

Everything above compares to *league-average* expectation, but schedules aren't average. The DVOA family of metrics (Football Outsiders' framework, and the spirit of any good power rating) adds the missing step: value each play against expectation *given the opponent*. Gaining 5 EPA/game against the league's best defense means more than against its worst.

The mechanics matter less than the concept, which you can apply to any stat in this warehouse: compute a unit's raw performance, compute what an average unit would have done against those same opponents (opponents' EPA/play allowed, say), and take the difference. Iterate a couple of times so the opponent ratings themselves are adjusted, and you've built a power rating. (Jarvis's own model does exactly this with EPA — see [How the Jarvis Model Works](/knowledge/model-primer).) Early in a season this adjustment is enormous — through four weeks, a team's schedule can be two standard deviations from neutral, and unadjusted EPA rankings in September routinely flatter whoever played the soft slate. The warehouse's strength-of-schedule and team-EPA views exist to make this correction easy rather than optional.

## Rate stats need minimums

Every rate stat is a fraction, and small denominators produce nonsense numerators. A QB with 30 attempts can post a 9.5 YPA; a back with 12 carries can average 7.1; a corner targeted six times can "allow" a 158.3 rating. None of it means anything yet. Reasonable floors this app applies (and you should too):

- QB season rates: ~160+ attempts (roughly half a season of starts)
- Receiver efficiency: ~40–50 targets
- RB efficiency: ~100 carries
- Pressure/coverage percentages: enough snaps that one play moves the number by well under a point

The deeper principle: different stats stabilize at different speeds. Completion percentage and target share settle within a few games; interception rate, touchdown rate, and fumble luck take *seasons* — which is why "regression candidate" lists built on TD rate outperform the takes built on highlight reels.

## Why single games lie

An NFL game is ~65 offensive snaps — a coin flipped 65 times with weighted sides. The best offense in football has bad days; the worst has good ones; a 60%-favorite loses two times in five. Add opponent quality, injuries, weather, turnover bounces (fumble *recovery* is nearly random even though fumble *frequency* is skill), and one game tells you almost nothing on its own. Practical defenses against being fooled:

1. **Weight priors heavily.** After Week 3, preseason expectations still beat season-to-date standings.
2. **Trust the stable stats first**: early-down EPA, success rate, CPOE, PROE — not turnover margin, red-zone percentage, or record in one-score games, all of which regress hard.
3. **Ask "what would this look like if it were noise?"** A 3-interception game moves a season interception rate by a couple percentage points; it happens to good QBs annually.
4. **Let sample sizes accumulate before narratives do.** The box score updates weekly; the truth updates slower.

This is also the honest frame for using any number in this app: EPA views, coach tendencies, referee splits — each answer states its seasons and filters precisely so you can judge the sample behind it. The metrics in this chapter are the sharpest public tools football has. The discipline about when to trust them is what actually separates analytics from numerology.
