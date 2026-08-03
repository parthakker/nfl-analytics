# The Fantasy Primer

Fantasy football is a market for predicting player production, and like any market it rewards the people who know what actually predicts. The core finding of two decades of fantasy analytics fits in one sentence: **opportunity predicts fantasy points, efficiency predicts regression.** Everything else — scoring formats, positional strategy, waiver tactics, playoff planning — is machinery built around that idea. This chapter covers the machinery, with the metrics grounded in the same warehouse that powers this app's [/leaders](/leaders) and [/players](/players) pages (which compute half-PPR natively, alongside standard and full PPR).

## Scoring formats

The scoring rules define the game you're actually playing, and they shift player values more than most managers appreciate. The standard skeleton:

| Category | Points |
|---|---|
| Passing yards | 1 per 25 (0.04/yd) |
| Passing TD | 4 (some leagues 6) |
| Interception | −2 (some leagues −1) |
| Rushing/receiving yards | 1 per 10 (0.1/yd) |
| Rushing/receiving TD | 6 |
| Reception | 0 (standard) / 0.5 (half-PPR) / 1 (PPR) |
| Fumble lost | −2 |
| Two-point conversion | 2 |

The reception column is the big lever. **PPR** (point per reception) was invented to close the gap between running backs and pass-catchers, and it works — sometimes too well: in full PPR, a 6-catch, 45-yard day (10.5 points) beats a 90-yard rushing day (9.0), which is why volume slot receivers and pass-catching backs jump a round or two in PPR drafts. **Half-PPR** is the popular compromise, and it's this app's default: receptions matter, but a catch is worth half a first down rather than a full one. Format changes rankings at the margins constantly — a target-hog possession receiver might be a WR2 in PPR and a WR3 in standard — so always know which game you're playing before trusting any ranking.

Two format variants change strategy wholesale:

- **Superflex / 2QB**: an extra lineup slot that can take a QB. Since QBs outscore everyone (they touch the ball every play), superflex turns them from a wait-until-round-8 position into first-round currency. In 1QB leagues, ~12 starting QBs are needed across the league and 32 exist — replacement level is high and QBs are cheap. In superflex, ~24 are needed and the math inverts.
- **TE premium** (1.5 PPR for tight ends) exists to make the TE wasteland interesting; it mostly concentrates value further in the elite ones.

## Opportunity beats efficiency

Here's the argument, and it's worth actually internalizing rather than nodding at. A player's fantasy output is volume × efficiency (touches × points per touch). Both matter in any given week. But they behave completely differently over time:

- **Volume is sticky.** A back who gets 20 touches this week very likely gets ~18–22 next week. Coaches allocate touches by role, and roles change slowly — with injuries and trades, not with box scores.
- **Efficiency is noisy.** Yards per carry, yards per target, and above all *touchdown rate* bounce violently week to week and regress hard toward player/scheme baselines. A wideout who scored on 3 of his last 10 targets did a real thing that already happened; it tells you almost nothing about his next 10 targets.

So when you're deciding between two players, the question is almost never "who's been more efficient?" — it's "who has the bigger, safer *role*?" The player with 9 targets and 8 points is a better bet than the player with 4 targets and 15 points, essentially always. Touchdowns are how fantasy points arrive; opportunity is how they're predicted. This is the same logic as the air-yards material in [The Analytics Primer](/knowledge), wearing a jersey.

### The volume metrics that matter

In rough order of predictive usefulness:

**Snap share** — percentage of the offense's plays a player is on the field for. The gatekeeper stat: nobody produces from the sideline. A rising snap share is often the earliest visible sign of a role change, a week before the box score notices. (70%+ is a locked-in starter for a WR; 60%+ is bell-cow territory for a back.)

**Target share** — percentage of team targets. The single best predictor of receiving production. Rules of thumb: 15% is startable-ish, 20% is solid WR2 territory, 25%+ is elite target-hog country. Target share also transfers across QB changes far better than raw production does — the role survives even when the passer doesn't.

**Route participation** — percentage of dropbacks on which the player ran a route. It's the receiving version of snap share and catches players whose target share understates them: a receiver running routes on 90% of dropbacks with a modest target share has room to grow; one hitting 22% target share on only 65% of routes is maxed out and fragile.

**Red-zone and goal-line usage** — touches inside the 20 and, especially, carries inside the 5. Touchdowns are the most valuable and least stable fantasy commodity, and goal-line work is the one lever that genuinely predicts them. Two backs can split a backfield 60/40, but if the 40% back gets the goal-line package, he can outscore his timeshare. The warehouse's red-zone usage view exists for exactly this hunt.

**Air yards and WOPR** — target share weighted by depth (WOPR = 1.5 × target share + 0.7 × air-yards share). Air yards are opportunity measured in potential yardage: a player with a big air-yards share and mediocre production is a *buy* (the opportunity is real, the results lagged), and vice versa. WOPR routinely identifies breakouts a few weeks before the points arrive.

The unified drill: when a player pops for 25 points, check the usage under it. Three targets and a long touchdown → fade. Nine targets, 85% routes, two red-zone looks → believe. Same score, opposite signals — and the usage columns in this warehouse's weekly stats let you check in seconds at [/players](/players).

## Positional scarcity and draft strategy

Draft value isn't about points scored; it's about **points over replacement** — production above what a freely available waiver player at the position provides. That one idea organizes all draft strategy:

- **QBs score the most and matter the least** (in 1QB). The 12th QB is nearly as good as the 5th, and streaming free-agent QBs against soft matchups is viable all season. Wait, unless it's superflex — then see above.
- **RB is the scarce, fragile position.** True three-down workloads have gotten rarer as teams commit to committees, so the handful of genuine bell cows carry enormous scarcity premiums — while also having the highest injury rate and fastest aging curve in fantasy. This tension defines every draft: RB-heavy starts capture scarcity; "Zero RB" starts (loading up on WRs early, harvesting RB volume later from injuries and waivers) exploit RB fragility instead. Both work in the right room; what doesn't work is drafting mid-round RBs whose committees cap them.
- **WR is deep but top-heavy**, and PPR formats deepen it further. The reliable move in modern drafts has been early-round WRs (safer, longer careers, target floors) over similarly priced RBs.
- **Elite TE or no TE.** The position is a barbell: a few every-week difference-makers, then a wasteland of 6-point hopefuls. Pay up for the elite tier or punt and stream — the middle rounds' "solid TE2" picks are where value goes to die.
- **Kickers and defenses are streaming positions.** Draft one of each, in the last two rounds, and treat the choices as weekly matchup plays all season. Any earlier pick at either spot is a donated round.

## Waivers and streaming

Leagues are won on the wire more than the draft. The operating principles:

- **Chase opportunity, not points.** The best waiver adds are usage spikes *before* the production shows: the backup stepping into an injured starter's snaps, the rookie whose route participation jumped to 85%. By the time the 25-point game happens, the player costs three times as much FAAB.
- **Handcuffs are lottery tickets on volume.** The direct backup to a bell-cow back is one injury from a top-15 workload. Handcuff *your own* studs selectively; stash other teams' high-upside backups when roster space allows.
- **FAAB budgeting** (free-agent auction bidding): the season is long, and the best claim of the year usually appears midseason. A workable frame — sub-5% bids for speculative stashes, 10–20% for solid starters, and 40%+ reserved for the rare league-winner (a clear bell-cow role opening for the rest of the season). Waiver-priority leagues are simpler: hold the top spot for role changes, not one-week matchups.
- **Stream aggressively** at QB (1QB), TE (if you punted), and DST. Defenses in particular are matchup products — target opponents with bad offensive lines and turnover-prone QBs, not last year's name brands.

## Playoff-schedule planning

Fantasy playoffs run weeks 15–17 in most leagues (championship week 17 — never week 18, when NFL teams rest starters with seeding locked). That means the season you're actually drafting for ends in a specific three-week window, and you can plan for it:

- **Check playoff-week matchups** when choosing between similar players in-season — a soft December slate is a real tiebreaker (though matchup projections made in August are weak; re-check in November when defenses have revealed themselves).
- **Weather arrives with the playoffs.** Wind and cold in outdoor northern stadiums suppress passing and kicking — worth a lean when starting borderline players or streaming kickers in December.
- **Beware Week 18-adjacent rest dynamics** creeping into week 17: teams that clinch early manage snaps. Contending fantasy teams should prefer players on NFL teams still fighting for seeding.
- **Trade deadlines reward foresight.** By your league's deadline (typically ~week 11–12), you know whether you're contending. Contenders should trade depth for ceiling and playoff schedules; sellers should harvest next year's assets or consolidate. The worst deadline move is standing pat out of attachment.

## The compounding loop

Put it together and fantasy is a weekly loop: read usage, not points (snap share, targets, routes, red zone at [/players](/players)); rank by opportunity-adjusted expectation, not last week's score (the half-PPR boards at [/leaders](/leaders)); spend waiver capital where roles just changed; and plan around the weeks 15–17 endgame from midseason on. None of it requires being smarter than your league mates — it requires being systematically less distracted by touchdowns, which is harder than it sounds and worth a title or two per decade.
