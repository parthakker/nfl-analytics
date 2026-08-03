# The Game

Everything in football analytics — EPA, win probability, fourth-down models — is built on top of a handful of physical and procedural facts: how big the field is, how possession works, and what each outcome is worth. Get these cold and the rest of the book gets much easier. This chapter is the ground floor.

## The Field and Its Geometry

An NFL field is 120 yards long and 53⅓ yards (160 feet) wide. The playing field itself is 100 yards between the goal lines, with a 10-yard end zone at each end.

![NFL field layout with yard lines, hashes, and end zones](/knowledge/field-layout.svg)

A few geometric details matter more than people realize:

| Feature | Spec | Why it matters |
|---|---|---|
| Field length | 100 yds + two 10-yd end zones | The basis for all yardage stats |
| Field width | 53⅓ yds (160 ft) | Wider than college feel? No — same width, but hashes differ |
| Hash marks | 70' 9" from each sideline, 18' 6" apart | Ball is spotted on or between the hashes after every play |
| Goalposts | Crossbar 10 ft high, uprights 18' 6" apart | Same width as the hashes — a kick from the hash is aimed "down the pipe" |
| Yard lines | Every 5 yds, numbered every 10 | Numbers ascend to the 50, then descend |

The **hash marks** are the quiet star here. In the NFL they're narrow — only 18½ feet apart, dead center of the field — so unlike college football, there's no true "wide side" advantage on most snaps. Every play starts from nearly the middle of the field, which is one reason NFL passing games can be so symmetrical and why "field position" in the NFL is almost entirely about the yard line, not the lateral spot.

The end zone being only 10 yards deep also shapes the game: back-shoulder throws, toe-tap sideline catches, and fade routes exist because the vertical space compresses near the goal line. Defenses shrink, windows shrink, and that's why red-zone efficiency is its own skill separate from moving the ball between the 20s.

## Downs and Distance

The offense gets **four downs to gain 10 yards**. Succeed and the count resets — a fresh set of downs, "1st and 10." Fail and the ball goes to the other team wherever it sits.

That's the whole engine. Everything else — play calling, punting, analytics-driven fourth-down aggression — is strategy layered on that four-attempt structure.

- **1st and 10**: the neutral state. Offenses can do anything, which is exactly why early-down pass rate is such a strong indicator of offensive identity.
- **2nd down**: the "and-distance" tells you how the first down went. 2nd and short is the offense's most dangerous down — they can take a deep shot with a free do-over waiting.
- **3rd down**: the money down. League-wide conversion rates fall off a cliff as distance grows — 3rd and short is roughly a coin flip in the offense's favor; 3rd and 10+ is a low-percentage prayer.
- **4th down**: historically an automatic punt or kick. The analytics era changed that — teams now go for it in situations that would've gotten a coach fired in 2005. (More in [Clock & Situational Football](/knowledge), and you can see live 4th-down aggressiveness by coach on the [Coaches](/coaches) page.)

One wrinkle worth knowing: penalties can create a **1st and goal** (inside the 10, where the goal line replaces the 10-yard target) or absurdities like "3rd and 33." The chains only care about the line to gain, wherever it is.

## Scoring: Every Way Points Go on the Board

| Play | Points | How it happens |
|---|---|---|
| Touchdown | 6 | Ball crosses the plane of the goal line in possession, or is caught/recovered in the end zone |
| Extra point (PAT kick) | 1 | Kick snapped from the 15-yard line (a ~33-yard kick) after a TD |
| Two-point conversion | 2 | One scrimmage play from the 2-yard line after a TD |
| Field goal | 3 | Place kick through the uprights on any down |
| Safety | 2 | Offense tackled, penalized, or fumbles out of bounds in its own end zone |
| Defensive two-point return | 2 | Defense returns a turnover or blocked kick on a conversion attempt all the way back |

Some texture on each:

**Touchdowns** are worth 6, but the *real* value of a TD is 6 plus the expected value of the try — which is why analysts talk about touchdowns being "worth about 7." The extra point moved back in 2015 (snap from the 15 instead of the 2), turning it from a formality into a ~94% proposition. That 6% miss rate is small but real, and in a league where something like one in twelve games is decided by exactly three points, it matters for [betting](/betting) totals and teasers.

**Two-point conversions** succeed a bit less than half the time league-wide, which makes the expected value of going for two roughly comparable to kicking — the decision is about game state, not cowardice vs. bravery. Trailing by 14 late? The modern move is to go for two after the *first* touchdown, so you know what you need before the second one.

**Field goals** are the great compromise of football: three points in exchange for admitting the drive failed. Kickers have gotten absurdly good — Justin Tucker's 66-yarder in 2021 is the record, and by 2024–25 kickers like Brandon Aubrey were attempting from the mid-60s without it feeling like a stunt. The analytics consequence: the "field goal range" line keeps creeping back, which changes fourth-down math near midfield.

**Safeties** are rare (a handful per season league-wide) but brutal: two points *and* the scoring team gets the ball back via a free kick. It's the only score where the team that got scored on has to kick.

**The fair catch kick** technically still exists — after a fair catch, a team may attempt a free kick field goal with no rush. You'll see one attempted maybe once every few seasons. It's a bar-bet rule, not a strategy.

## How Possession Changes Hands

Every change of possession falls into one of these buckets:

1. **Punt** — the voluntary surrender. The offense trades the ball for field position. (Why that trade is often smarter than it looks — and often dumber — is covered in [Special Teams](/knowledge).)
2. **Turnover** — interception or lost fumble. The single most game-swinging event in football; a turnover is typically worth about 4–5 points of expected value swing, which is why turnover margin correlates so strongly with winning and why it's also so noisy year to year.
3. **Turnover on downs** — failing on fourth down. The opponent takes over at the dead-ball spot, which is what makes a failed 4th-and-1 at your own 40 so painful: it's a turnover with no punt yardage attached.
4. **Missed field goal** — the opponent takes over at the *spot of the kick* (not the line of scrimmage), which is roughly 7–8 yards behind where the drive stalled. A missed 55-yarder hands the opponent the ball near midfield. Long field goal attempts are genuinely risky, not free rolls.
5. **Score** — after any touchdown or field goal, the scoring team kicks off.
6. **Safety** — the team that conceded it free-kicks from its own 20.
7. **Half/game boundaries** — the second half opens with a kickoff to whichever team deferred (almost every coach defers now, banking the "double-up" chance of scoring before half and receiving after).

## Game Flow: Quarters, Clock, and Halftime

A game is four **15-minute quarters** with a 12-minute halftime. Teams switch end zones every quarter, which matters for wind and for kickers — a coach choosing to defend a particular goal in the fourth quarter is thinking about a potential game-winning kick.

The clock, not the scoreboard, is the real opponent for a trailing team:

- The **game clock** stops on incompletions, out-of-bounds plays (with in-bounds restarts differing by game situation), scores, and changes of possession.
- The **play clock** is 40 seconds from the end of the previous play (25 in certain administrative situations). Teams that snap with 15+ seconds left are playing fast on purpose; teams that snap at :01 are bleeding clock on purpose. Tempo is a weapon in both directions.
- The **two-minute warning** in each half is a free timeout that shapes all late-half strategy.

A typical NFL game features around 125–135 offensive snaps combined, spread over three-plus hours — but only about 11 minutes of actual ball-in-play action. Football is a game of discrete decisions with long deliberation windows, which is precisely why it's so friendly to analytics.

## Overtime — Including the 2025 Changes

Overtime rules diverged between regular season and playoffs for years, and 2025 brought them closer together. Here's the current state:

| | Regular season (2025) | Playoffs |
|---|---|---|
| Period length | 10 minutes | 15 minutes |
| Both teams guaranteed a possession? | **Yes** — new for 2025, even if the first team scores a TD | Yes (since the 2022 rule change) |
| After both teams have possessed | Next score wins | Next score wins |
| Can it end in a tie? | Yes, if still tied when time expires | No — additional periods until a winner |
| First-play safety | Ends it immediately | Ends it immediately |

Before 2025, a first-possession touchdown ended a regular-season game instantly — meaning the coin toss carried real win-probability weight. The 2025 change (guaranteeing both teams a possession, playoff-style, while keeping the 10-minute period) reduced the toss advantage but created new strategy: some coaches now consider *kicking off* first in OT to get the "answer" possession with full knowledge of what they need — the strategy the Chiefs famously used to win Super Bowl LVIII in overtime against the 49ers.

Ties are rare but real — with only 10 minutes and both teams guaranteed the ball, running out of clock is genuinely possible, and a couple of ties per season is the norm. If you bet totals or play [fantasy](/knowledge), OT is pure variance injection: free extra possessions nobody priced in.

## The Officials on the Field

Seven officials work every NFL game, each with a defined position and jurisdiction:

| Official | Where they line up | Primary responsibilities |
|---|---|---|
| Referee | Behind the offense, QB's throwing side | Crew chief ("white hat"), QB protection, announcements |
| Umpire | Offensive backfield (moved from behind the DL for safety) | Holding on interior line, illegal equipment, spotting the ball |
| Down Judge | Sideline, at the line of scrimmage | Chain crew, offside/encroachment, boundary calls |
| Line Judge | Opposite sideline, at the line | Same as down judge, opposite side; illegal motion |
| Field Judge | Deep, on the line judge's side | Deep coverage, pass interference, sideline catches |
| Side Judge | Deep, on the down judge's side | Mirror of the field judge |
| Back Judge | Deepest, middle of the field | Play clock, deep middle coverage, field goals (with FJ) |

The referee is the only one whose name casual fans learn, but crews travel together and develop measurable tendencies — some throw 30% more flags than others, some call defensive holding tight, some let secondaries play. That's not conspiracy, it's just humans with different judgment thresholds, and it's quantifiable: penalty rates, over/under results, and home-team bias by head referee are all tracked on this app's [Refs](/refs) page. When a referee assignment is announced for a game you care about, it's worth thirty seconds of your time — the data says crews are not interchangeable.

Replay review sits on top of the on-field crew: scoring plays and turnovers are automatically reviewed, coaches get two challenges (a third if both succeed), and since the replay-assist era began, obvious errors on objective calls can be fixed from the booth without a full stoppage.

## Why This Chapter Matters for the Rest of the Book

Almost every number in the [Analytics Primer](/knowledge) is denominated in the units defined here: yards on this field, points from that scoring table, possessions bounded by these change-of-possession rules. Expected points is literally "given down, distance, and field position, what's the average of the next scoring outcome?" — a question you can only ask once you know what the downs, distances, and scores are. You now do.
