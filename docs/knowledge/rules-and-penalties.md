# Rules & Penalties

Penalties are where football's rulebook stops being trivia and starts moving win probability. A single defensive pass interference call can hand an offense 40 yards — more than most drives gain on their own — while a false start on 3rd-and-2 can quietly kill a possession. This chapter covers the penalties that actually matter, what each one costs in yards and downs, why some are catastrophically more expensive than others, and how replay and challenges decide which mistakes can even be fixed. Officiating crews also call these at meaningfully different rates, which is why this app tracks crews individually at [/refs](/refs).

## The penalty table

Every penalty has three components: a yardage cost, a down consequence (replay the down, loss of down, or automatic first down), and an enforcement spot. Here are the ones you'll see week in and week out:

| Penalty | Against | Yards | Down consequence | Notes |
|---|---|---|---|---|
| False start | Offense | 5 | Replay down | Dead-ball foul; play never happens |
| Offside / encroachment | Defense | 5 | Replay down | Encroachment (contact) is dead-ball; plain offside lets the play run — free play for the offense |
| Neutral zone infraction | Defense | 5 | Replay down | Defender's jump makes a lineman flinch; dead ball |
| Delay of game | Offense | 5 | Replay down | Play clock hits zero |
| Offensive holding | Offense | 10 | Replay down | The most common flag in football |
| Defensive holding | Defense | 5 | **Automatic first down** | Grabbing a receiver beyond 1 yard, before the ball is thrown |
| Illegal contact | Defense | 5 | **Automatic first down** | Contact beyond 5 yards while QB is in the pocket |
| Defensive pass interference | Defense | **Spot foul** | **Automatic first down** | In the end zone: ball placed at the 1 |
| Offensive pass interference | Offense | 10 | Replay down | No loss of down |
| Roughing the passer | Defense | 15 | **Automatic first down** | Added to the end of the play if the pass completes |
| Face mask | Either | 15 | Auto first down if defensive | Grasp-and-twist |
| Unnecessary roughness / unsportsmanlike | Either | 15 | Auto first down if defensive | Two unsportsmanlike fouls = ejection |
| Intentional grounding | Offense | 10 (or spot) + **loss of down** | Loss of down | In own end zone: safety |
| Illegal block in the back | Either (usually return team) | 10 | — | The classic punt-return killer |
| Illegal formation / illegal shift | Offense | 5 | Replay down | Fewer than 7 on the line, or motion not set |
| Defensive 12 men on the field | Defense | 5 | Replay down | Free play if snapped; dead ball if lined up |
| Taunting | Either | 15 | Auto first if defensive | Point of emphasis era, called sporadically |

A few things jump out of that table once you read it with an analytics eye, so let's walk through them.

## Spot fouls vs. yardage fouls

Most penalties are **fixed-yardage fouls**: 5, 10, or 15 yards from the previous spot (or the spot of the foul, for things like holding downfield). Their cost is capped and predictable.

**Spot fouls** are a different animal. Defensive pass interference is enforced at the spot of the foul — wherever the contact occurred, that's where the ball goes. A DPI on a deep shot 45 yards downfield is a 45-yard penalty. This is the single most important asymmetry in the penalty rulebook, and it's uniquely American: college football caps DPI at 15 yards, which is why NFL offenses throw deep "flag-bait" balls in a way college offenses don't.

The related half-rule: DPI **in the end zone** places the ball at the 1-yard line. A defender who's beaten on a fade to the goal line faces a brutal choice — let the catch happen, or commit the foul and concede 1st-and-goal at the 1, which is nearly a touchdown anyway.

## DPI economics

Think of DPI in expected-points terms (see [The Analytics Primer](/knowledge) for the EPA framework). A deep incompletion is worth roughly nothing; a deep completion is worth several expected points. DPI converts the incompletion outcome into the completion outcome — the offense gets the yardage *as if the ball were caught*, plus an automatic first down. That makes a deep ball with any contact a heads-I-win, tails-you-lose proposition: catch it, or draw the flag.

Consequences that follow logically:

- **Deep shots have hidden value.** A 15% completion probability on a 50-yard throw understates its worth, because some fraction of the "incompletions" come back as spot-foul DPIs.
- **Defensive backs are coached to play through the receiver's hands** and to avoid early contact at all costs — a 5-yard defensive holding call (grabbing before the throw) is *vastly* cheaper than DPI (after the throw). When you see a corner tackle a receiver 8 yards downfield before the ball arrives, that's not panic; it's arithmetic. Holding + automatic first down beats a 40-yard spot foul.
- **DPI is judgment-heavy and crew-dependent.** It is among the highest-variance calls in football, and after a one-season experiment in 2019, it is **not reviewable**. What the on-field official calls, stands.

## Holding: the everywhere foul

Offensive holding is the most-called penalty in the NFL, and the old cliché — "you could call holding on every play" — is roughly true. Officials are trained to flag holds that are **material**: at the point of attack, or that clearly restrict a defender who has beaten his block. That materiality standard is exactly why holding rates vary by crew more than almost any other flag; it's a judgment call made 60+ times a game and thrown maybe 2–4 times.

Cost-wise, offensive holding is 10 yards with a replayed down, and it's a drive-killer disproportionate to its yardage: 1st-and-10 becomes 1st-and-20, and offenses convert long-yardage series at low rates. On big runs, a hold behind the play erases the gain entirely — the down is replayed from 10 back.

**Defensive holding** is only 5 yards but carries the automatic first down, which is the real payload. On 3rd-and-12, a defensive hold on an underneath receiver wipes out a stop and extends the drive. Defensively, downs are the currency; yards are just the denomination.

## False start vs. offsides: who moved first, and does the play count?

These two 5-yarders are mirror images with one crucial difference — whether the play happens.

- **False start** (offense moves before the snap) is a **dead-ball foul**. The whistle blows, no play occurs, 5 yards back. There is no upside case.
- **Offside** (defender across the line at the snap, no contact) is a **live-ball foul** — the play runs, and the offense gets a **free play**. Quarterbacks who spot a defender jumping will snap it immediately and launch downfield: worst case, decline-proof 5 yards; best case, a touchdown that counts. Aaron Rodgers built a highlight genre out of this.
- **Encroachment** (defender makes contact before the snap) and **neutral zone infraction** (defender's jump causes an offensive lineman to flinch) are the dead-ball defensive versions — 5 yards, no play.

Free-play situations are one of the few times you'll see a smart offense *want* a penalty on the field.

## Reviewable vs. non-reviewable

Replay review covers **objective, observable facts**, not judgment calls. The clean mental model:

**Reviewable:** catch/no-catch, ball spots and line-to-gain, in/out of bounds, down by contact, fumbles and recoveries, whether a pass was forward or backward, touching of a kick, number of players on the field, and the game clock in limited situations.

**Automatically reviewed (booth-initiated, no challenge needed):** every scoring play and every turnover. Also anything inside the final two minutes of each half and all of overtime — coaches *cannot* challenge in those windows; only the replay official can trigger a review.

**Not reviewable:** nearly all fouls — pass interference (again: the 2019 experiment died after one season), holding, roughing the passer. The notable carve-outs are objective components of fouls: replay can confirm whether a hit was on a defenseless receiver's head, and the **replay assist** system (expanded through the mid-2020s) lets the booth proactively fix clear, objective errors — spots, ticking clocks, and, in recent seasons, picking up flags for things like facemask when video plainly shows no foul occurred. Replay assist can take a flag *off*; it cannot put one *on*.

## Challenge rules

- Coaches get **two challenges** per game, thrown via the red flag, only when the clock isn't inside the two-minute windows.
- A failed challenge costs a **timeout**; you must have a timeout available to challenge at all.
- Since the 2025 rule change, a coach earns a **third challenge if at least one of the first two succeeds** (previously both had to succeed — a bar so high the third challenge almost never existed).
- The bar for reversal is "clear and obvious visual evidence." Ties go to the on-field call, which is why challenge success rates hover near a coin flip and why good coaches wait for their video assistant's verdict before throwing.

Challenge strategy is expected-value math like everything else: a challenge risks one timeout to win back whatever the play was worth. Challenging a 3-yard spot in the second quarter is lighting EV on fire; challenging a turnover-worthy fumble is nearly always right, though those now get reviewed automatically anyway.

## Crews call games differently

The rulebook is uniform; its enforcement is not. Officiating crews are stable units that travel together all season, and they develop measurable tendencies — some crews throw 12+ flags a game, others closer to 8; some call offensive holding at twice the rate of others; DPI frequency varies enough to matter for totals and for deep-passing game scripts. Crew assignments are typically known a few days before kickoff, and sharp bettors price them in, particularly for totals (more flags → more clock stoppages and extended drives) and for teams whose style collides with a crew's pet call.

This app computes exactly this from the officials data (2015+): per-referee penalty rates, over/under results, and home-team bias, at [/refs](/refs). The honest caveats built into that page apply anywhere you use crew data: referee samples are small (a head ref works ~17 games a year), penalty rates are noisy year to year, and the head referee is one of seven officials — attribute tendencies to the *crew*, gently, not to one man, strongly.

## The meta-lesson

Penalties look like randomness, but they're a system with prices. Downs are worth more than yards (automatic first downs are the tell). Spot fouls dwarf fixed-yardage fouls (DPI is the tell). Dead-ball fouls are pure loss; live-ball defensive fouls create free options. And the enforcement layer — judgment calls, crew tendencies, what replay can and can't touch — adds a human variance term that you can't eliminate but can measure. That's the rulebook read like an analyst.
