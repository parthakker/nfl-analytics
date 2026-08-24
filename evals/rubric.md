# Human scoring rubric

Score each transcript 0-2 per axis while skimming (0 = fails, 1 = adequate,
2 = strong). Note anything surprising in the run dir's summary.md.

| Axis | 0 | 2 |
|---|---|---|
| **Correct numbers** | wrong or invented values | every number traceable to a tool call |
| **Filters cited** | no seasons/filters stated | filters stated inline, reproducible |
| **Right tool, right depth** | wandered, wrong tool, or re-queried needlessly | shortest sensible tool path |
| **Answer shape** | wall of prose | leads with the answer; compact table for numbers; phone-width friendly |
| **Domain honesty** | overclaims (model as oracle, stale data as live, invented refs) | states caveats: sample size, data floors, model-vs-market, snapshot age |
| **Betting relevance** *(betting questions only)* | generic stats dump | speaks to the actual decision: side, price, fees, edge size |

Red flags to always mark: hallucinated player/team/ref names, season_type
unfiltered (gotcha #1), ignoring the fee-adjusted actionable concept,
pretending to live data the warehouse doesn't have.
