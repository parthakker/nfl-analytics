---
name: new-analysis
description: Answer an NFL analytics question with reproducible SQL — the standard analysis workflow with citations and sanity checks.
argument-hint: "[the question]"
---

# Analysis workflow

1. Load `warehouse-queries` (grains, traps) — pick tables/views; prefer views
   over raw tables when one fits (v_team_games, v_matchup_games,
   v_player_stats_week_all, v_game_weather...).
2. State filters explicitly before running: seasons, season_type, play_type,
   minimums. Defaults: REG only, pass/run plays, sensible attempt minimums.
3. Run read-only. Sanity-check the result (row counts, a known reference
   value, era coverage) before presenting.
4. Present: answer first, then the filters used ("2018–2025 REG, min 160
   att"), then caveats (coverage floors, small samples). Cite enough that the
   query could be re-run from the answer alone.
5. If the question will recur, propose promoting it to a view (/new-view).
