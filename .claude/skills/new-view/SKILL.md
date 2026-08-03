---
name: new-view
description: Add a derived warehouse view properly (SQL, dictionary, invariant test, catalog). Use when creating or materially changing a v_* view.
argument-hint: "[view name + purpose]"
---

# New warehouse view checklist

1. Load the `warehouse-queries` skill first (grains, join keys, traps).
2. SQL into the VIEWS dict in `scripts/build_views.py` — WITH a leading
   comment stating the grain and any convention (team-perspective spread,
   ref_key aggregation, canon_team usage). Tables the view needs must be
   created before the VIEWS loop.
3. `python -m nfl_analytics.cli views` — confirm the row count printed for
   the new view is plausible.
4. Invariant test in `tests/warehouse/` (row floor, symmetry/identity, or a
   pinned known value — whatever would catch silent corruption). Must pass on
   the CI fixture too (derive seasons from the DB; pytest.skip if the fixture
   slice can't contain the data).
5. Dictionary: add/extend the relevant `docs/dictionary/*.md`.
6. Catalog: one line in `.claude/skills/warehouse-queries/SKILL.md` views list.
7. If the fixture needs the view's source tables: check scripts/make_fixture.py
   SLICED/FULL_COPY lists, rebuild via `nfl fixture` if so.
