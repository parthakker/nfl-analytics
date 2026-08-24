/** Page-aware starter questions for the chat empty state.
 *
 *  Phrased to stay answerable year-round: they lean on last season, career
 *  history, and "the upcoming slate" rather than assuming games are on this
 *  week. The default set covers the four usage moments — pregame, gameday,
 *  postgame/learning, fantasy. */

const DEFAULT = [
  "Break down the most interesting game on the upcoming slate",
  "What games are on today and where are the closest spreads?",
  "Explain EPA and success rate like I'm new to analytics",
  "Which players are trending up in usage over the last month of last season?",
];

export function startersFor(pathname: string): string[] {
  if (pathname.startsWith("/betting")) {
    return [
      "Walk this week's betting board: which games stand out and why?",
      "Where do Vegas and Kalshi disagree enough to be actionable right now?",
      "Which lines have moved the most since they opened, and what likely drove the move?",
      "Which referee assignments carry betting-relevant tendencies?",
    ];
  }
  if (pathname.startsWith("/players") || pathname.startsWith("/player/")) {
    return [
      "Which players are trending up in usage over the last month of last season?",
      "Who looks like a buy-low: efficiency strong but production lagging?",
      "Who led the league in red-zone target share last season?",
      "Scout a star for me: pick an elite receiver and break down their profile",
    ];
  }
  if (pathname.startsWith("/team/")) {
    const code = decodeURIComponent(pathname.split("/")[2] ?? "").toUpperCase();
    const team = /^[A-Z]{2,3}$/.test(code) ? `the ${code}` : "this team";
    return [
      `How is ${team} trending: their last five games, and how they won or lost?`,
      `How tough is ${team}'s upcoming schedule compared to the rest of the league?`,
      `What are ${team}'s coaching tendencies: pass rate, pace, and fourth-down aggression?`,
      `How much travel does ${team} face this season, and does travel actually matter?`,
    ];
  }
  if (pathname.startsWith("/knowledge")) {
    return [
      "Explain the Cover 2 defense and how offenses attack it",
      "What does the mike linebacker do, and why do quarterbacks point at him before the snap?",
      "What's the difference between EPA and success rate, and when should I use each?",
      "How does fantasy scoring work: standard vs half-PPR vs full PPR?",
    ];
  }
  return DEFAULT;
}
