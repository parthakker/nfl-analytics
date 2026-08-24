---
paths:
  - "data/stadiums.json"
  - "data/coaches_meta.json"
  - "data/betting_rules.json"
---
# Hand-curated data rules

These files are HAND-EDITED and never overwritten by any refresh script. They
are the only files under data/ tracked in git — treat edits like code.

**stadiums.json**: venue db powering game_venues/travel. `venue_id` reuses
nflverse stadium_id where stable; minted ids (IRE00, BER00, MAD00, PAR00,
RIO00, AUS00) for venues nflverse never assigned. `aliases` must contain every
`schedules.stadium` string observed for the venue — name-matching is how
Neutral games resolve. `et_offset` = hours behind ET (negative = ahead, e.g.
London -5). `game_overrides` pins game_ids whose schedules venue data is
wrong (the seven 2025 internationals carry the home team's US stadium — check
new international seasons for the same bug before trusting names).

**coaches_meta.json**: HC/OC/DC + scheme identity per team. HC auto-derived
from schedules at creation; OC/DC mostly unrecorded — fill freely as facts
are learned.

**betting_rules.json**: the curated betting-rules catalog evaluated by
`src/nfl_analytics/rules.py` (`/api/rules`). Fields, ops, markets and sides
are a CLOSED namespace validated at load — an unknown anything is a hard
error naming the rule id, and rule content is never interpolated into SQL.
Add fields by extending `FIELDS` (and the facts SQL) in rules.py first.
Rules on kalshi/line-movement fields are live-only: no backtest until
snapshot history accrues (tracking since 2026-08). After editing: `pytest
tests/unit/test_rules.py -q` (validates the file loads clean).

Judge a backtest by its `signal`, not its ROI: the summary scores win rate in
standard errors above breakeven and grades it noise / weak / strong, with the
strong bar at z=2.6 so it survives having looked at the whole catalog. A rule
the history kills stays in the file with `enabled: false` and a note saying
what it went — deleting it just invites re-seeding the same idea.

After editing stadiums/coaches_meta: run `nfl views` (rebuilds
stadiums/game_venues + travel sanity checks) then `pytest
tests/warehouse/test_venues.py tests/warehouse/test_travel.py -q`. An
unresolved-venue warning in the build output means a missing alias/override.
