---
paths:
  - "data/stadiums.json"
  - "data/coaches_meta.json"
---
# Hand-curated data rules

Both files are HAND-EDITED and never overwritten by any refresh script. They
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

After editing either file: run `nfl views` (rebuilds stadiums/game_venues +
travel sanity checks) then `pytest tests/warehouse/test_venues.py
tests/warehouse/test_travel.py -q`. An unresolved-venue warning in the build
output means a missing alias/override.
