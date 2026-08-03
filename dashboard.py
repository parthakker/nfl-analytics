"""NFL Analytics dashboard v2 — logos, divisions, team pages, embedded chat.

Run:  python -m streamlit run dashboard.py
(or the "NFL Dashboard" desktop shortcut)
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DB = ROOT / "nfl.duckdb"
NEWS_DB = ROOT / "news.duckdb"
sys.path.insert(0, str(ROOT / "src"))
from nfl_analytics.teams_meta import TEAMS, DIVISIONS, logo_url, color, name  # noqa: E402

# dataviz reference palette
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK_MUTED, GRID = "#898781", "#e1e0d9"

st.set_page_config(page_title="NFL Analytics", page_icon="🏈", layout="wide")
st.markdown("""
<style>
  .block-container { padding-top: 2.2rem; }
  div[data-testid="stSidebarNav"] { display: none; }
  .team-banner { border-radius: 12px; padding: 18px 24px; color: white;
                 display: flex; align-items: center; gap: 18px; }
  .team-banner img { height: 64px; }
  .team-banner h2 { margin: 0; color: white; }
  .division-header { font-size: 0.85rem; font-weight: 700; color: #52514e;
                     text-transform: uppercase; letter-spacing: .06em;
                     margin: 10px 0 2px 0; }
  div[data-testid="stHorizontalBlock"] { align-items: center; }
  .stButton button { border: none; background: transparent; text-align: left;
                     padding: 2px 6px; font-weight: 600; }
  .stButton button:hover { color: #2a78d6; background: #f0f4fa; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    con = duckdb.connect(str(DB), read_only=True)
    try:
        return con.execute(sql, list(params)).fetchdf()
    finally:
        con.close()


@st.cache_data(ttl=300, show_spinner=False)
def qnews(sql: str, params: tuple = ()) -> pd.DataFrame:
    con = duckdb.connect(str(NEWS_DB), read_only=True)
    try:
        return con.execute(sql, list(params)).fetchdf()
    finally:
        con.close()


# ---------- navigation state ----------
if "page" not in st.session_state:
    st.session_state.page = "League"
if "team" not in st.session_state:
    st.session_state.team = "DET"

PAGES = ["League", "Team", "Players", "Leaders", "Schedule", "News", "Chat"]
ICONS = {"League": "🏈", "Team": "🛡️", "Players": "👤", "Leaders": "🏆",
         "Schedule": "📅", "News": "📰", "Chat": "💬"}

st.sidebar.title("🏈 NFL Analytics")
choice = st.sidebar.radio("Navigate", PAGES,
                          index=PAGES.index(st.session_state.page),
                          format_func=lambda p: f"{ICONS[p]}  {p}",
                          label_visibility="collapsed")
if choice != st.session_state.page:
    st.session_state.page = choice
page = st.session_state.page


def goto_team(code: str) -> None:
    st.session_state.team = code
    st.session_state.page = "Team"


RECORDS = q("""
    SELECT team, count(*) AS g, sum(win) AS w
    FROM v_team_games WHERE season = 2025 AND season_type = 'REG'
    GROUP BY team
""").set_index("team")


def record_str(code: str) -> str:
    if code not in RECORDS.index:
        return ""
    r = RECORDS.loc[code]
    return f"{int(r.w)}–{int(r.g - r.w)}"


# ---------- League ----------
if page == "League":
    st.title("The League")
    st.caption("2025 regular-season records. Click any team to dive in.")
    conf_cols = st.columns(2)
    for ci, conf in enumerate(["AFC", "NFC"]):
        with conf_cols[ci]:
            st.subheader(conf)
            for div in ["East", "North", "South", "West"]:
                st.markdown(f'<div class="division-header">{conf} {div}</div>',
                            unsafe_allow_html=True)
                codes = sorted(DIVISIONS[f"{conf} {div}"],
                               key=lambda c: -(RECORDS.loc[c].w if c in RECORDS.index else 0))
                for code in codes:
                    c1, c2, c3 = st.columns([0.13, 0.62, 0.25])
                    c1.image(logo_url(code, 500), width=34)
                    if c2.button(name(code), key=f"btn_{code}"):
                        goto_team(code)
                        st.rerun()
                    c3.markdown(f"**{record_str(code)}**")

# ---------- Team ----------
elif page == "Team":
    codes = list(TEAMS)
    team = st.selectbox("Team", codes, index=codes.index(st.session_state.team),
                        format_func=name, label_visibility="collapsed")
    st.session_state.team = team
    st.markdown(f"""
      <div class="team-banner" style="background:{color(team)}">
        <img src="{logo_url(team)}"/>
        <div><h2>{name(team)}</h2>
        <div>2025: {record_str(team)} &nbsp;•&nbsp; {TEAMS[team][1]} {TEAMS[team][2]}</div></div>
      </div>""", unsafe_allow_html=True)
    st.write("")

    tab_over, tab_roster, tab_coach, tab_news, tab_sched = st.tabs(
        ["Overview", "Roster", "Coaching", "News", "2026 Schedule"])

    with tab_over:
        season = st.selectbox("Season", list(range(2025, 2006, -1)))
        rec = q("""
            SELECT count(*) g, sum(win) w, round(avg(points_for),1) pf,
                   round(avg(points_against),1) pa
            FROM v_team_games WHERE team=? AND season=? AND season_type='REG'
        """, (team, season)).iloc[0]
        sos = q("""
            SELECT rank() OVER (ORDER BY opp_avg_win_pct DESC) rk,
                   round(opp_avg_win_pct,3) v
            FROM v_strength_of_schedule WHERE season=? QUALIFY team=?
        """, (season, team))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Record", f"{int(rec.w)}–{int(rec.g - rec.w)}" if rec.g else "—")
        c2.metric("Points/game", rec.pf)
        c3.metric("Allowed/game", rec.pa)
        c4.metric("Sched. difficulty", f"#{int(sos.iloc[0].rk)}/32" if not sos.empty else "—")
        epa = q("""
            SELECT g.week,
                   round(avg(p.epa) FILTER (WHERE p.posteam=?),3) AS "Offense",
                   round(avg(p.epa) FILTER (WHERE p.defteam=?),3) AS "Defense"
            FROM play_by_play p JOIN games g USING (game_id)
            WHERE p.season=? AND p.play_type IN ('pass','run')
              AND (p.posteam=? OR p.defteam=?)
            GROUP BY g.week ORDER BY g.week
        """, (team, team, season, team, team))
        if not epa.empty:
            long = epa.melt("week", ["Offense", "Defense"], var_name="side", value_name="epa")
            st.altair_chart(
                alt.Chart(long).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=60))
                .encode(x=alt.X("week:O", title="Week",
                                axis=alt.Axis(labelColor=INK_MUTED, gridColor=GRID)),
                        y=alt.Y("epa:Q", title="EPA per play",
                                axis=alt.Axis(labelColor=INK_MUTED, gridColor=GRID)),
                        color=alt.Color("side:N", title=None,
                                        scale=alt.Scale(domain=["Offense", "Defense"],
                                                        range=[BLUE, ORANGE]),
                                        legend=alt.Legend(orient="top")),
                        tooltip=["week", "side", alt.Tooltip("epa:Q", format=".3f")])
                .properties(height=260), width="stretch")
            st.caption("Offense: higher is better. Defense: lower is better (what they allowed).")

    with tab_roster:
        roster = q("""
            SELECT any_value(jersey_number)::int AS num, full_name AS player,
                   any_value(position) AS pos, any_value(status) AS status,
                   any_value(college) AS college, any_value(years_exp)::int AS exp
            FROM rosters_weekly WHERE season = 2026 AND team = ?
            GROUP BY full_name ORDER BY pos, num
        """, (team,))
        st.caption(f"2026 roster — {len(roster)} players (preseason; churns until cut-down day)")
        pos = st.multiselect("Filter position", sorted(roster["pos"].dropna().unique()))
        st.dataframe(roster[roster["pos"].isin(pos)] if pos else roster,
                     width="stretch", hide_index=True, height=480)

    with tab_coach:
        cur = q("""
            SELECT any_value(home_coach) c FROM schedules
            WHERE season=2026 AND home_team=?
        """, (team,)).iloc[0].c
        st.metric("2026 head coach", cur or "—")
        hist = q("""
            SELECT season, any_value(coach) AS coach, count(*) AS games,
                   sum(win)::int AS wins, round(avg(points_for),1) AS ppg
            FROM (SELECT season, week, coach, win, points_for
                  FROM v_team_games WHERE team=? AND season_type='REG')
            GROUP BY season ORDER BY season DESC
        """, (team,))
        st.dataframe(hist, width="stretch", hide_index=True)
        st.caption("Coach shown is the one who coached most games that season.")

    with tab_news:
        news = qnews("""
            SELECT strftime(published_ts, '%b %d %H:%M') AS at, source, headline, url
            FROM news
            WHERE list_contains(teams, ?) OR headline ILIKE '%' || ? || '%'
            ORDER BY published_ts DESC NULLS LAST LIMIT 30
        """, (team, name(team).split()[-1]))
        for r in news.itertuples():
            src = "🏟️ team site" if r.source == "team_site" else "📺 ESPN"
            st.markdown(f"**[{r.headline}]({r.url})**  \n"
                        f"<small>{r.at} · {src}</small>", unsafe_allow_html=True)

    with tab_sched:
        st.dataframe(q("""
            SELECT week, strftime(gameday, '%a %b %d') AS date,
                   CASE WHEN home_team=? THEN 'vs ' || away_team
                        ELSE '@ ' || home_team END AS opponent,
                   CASE WHEN spread_line IS NULL THEN ''
                        WHEN (home_team=? AND spread_line>0) OR (away_team=? AND spread_line<0)
                        THEN 'favored by ' || abs(spread_line)
                        ELSE 'underdog by ' || abs(spread_line) END AS line
            FROM schedules WHERE season=2026 AND (home_team=? OR away_team=?)
            ORDER BY week
        """, (team, team, team, team, team)), width="stretch", hide_index=True)

# ---------- Players ----------
elif page == "Players":
    st.title("Player explorer")
    nm = st.text_input("Search a player", placeholder="e.g. Jahmyr Gibbs …")
    if nm:
        hits = q("""
            SELECT gsis_id, display_name, position, latest_team
            FROM players WHERE display_name ILIKE '%' || ? || '%'
            ORDER BY (last_season IS NULL), last_season DESC LIMIT 8
        """, (nm,))
        if hits.empty:
            st.warning("No player found.")
        else:
            labels = [f"{r.display_name} ({r.position}, {r.latest_team})" for r in hits.itertuples()]
            pick = st.selectbox("Matches", labels)
            gsis = hits.iloc[labels.index(pick)]["gsis_id"]
            seasons = q("""
                SELECT season, count(*) games, sum(passing_yards)::int pass_yds,
                       sum(rushing_yards)::int rush_yds, sum(receptions)::int rec,
                       sum(receiving_yards)::int rec_yds,
                       round(sum(fantasy_points_ppr),1) ppr
                FROM v_player_stats_week_all
                WHERE player_id=? AND season_type='REG' AND week IS NOT NULL
                GROUP BY season ORDER BY season DESC
            """, (gsis,))
            st.dataframe(seasons, width="stretch", hide_index=True)
            pn = qnews("""
                SELECT strftime(published_ts,'%b %d') at, headline, url FROM news
                WHERE list_contains(players, ?) ORDER BY published_ts DESC LIMIT 5
            """, (gsis,))
            if not pn.empty:
                st.subheader("Recent news")
                for r in pn.itertuples():
                    st.markdown(f"- [{r.headline}]({r.url}) <small>({r.at})</small>",
                                unsafe_allow_html=True)

# ---------- Leaders ----------
elif page == "Leaders":
    st.title("League leaders")
    c1, c2, c3 = st.columns(3)
    season = c1.selectbox("Season", list(range(2025, 2006, -1)))
    cat = c2.selectbox("Category", ["Fantasy (PPR)", "Passing", "Rushing", "Receiving"])
    min_g = c3.slider("Minimum games", 1, 17, 8)
    metric = {"Fantasy (PPR)": ("round(sum(fantasy_points_ppr),1)", "PPR points"),
              "Passing": ("sum(passing_yards)::int", "passing yards"),
              "Rushing": ("sum(rushing_yards)::int", "rushing yards"),
              "Receiving": ("sum(receiving_yards)::int", "receiving yards")}[cat]
    st.dataframe(q(f"""
        SELECT player_display_name AS player, any_value(position) pos,
               any_value(recent_team) team, count(*) games, {metric[0]} AS "{metric[1]}"
        FROM v_player_stats_week_all
        WHERE season=? AND season_type='REG'
        GROUP BY player_display_name HAVING count(*) >= ?
        ORDER BY 5 DESC LIMIT 25
    """, (season, min_g)), width="stretch", hide_index=True)

# ---------- Schedule ----------
elif page == "Schedule":
    st.title("Schedule & lines")
    c1, c2 = st.columns(2)
    season = c1.selectbox("Season", list(range(2026, 2006, -1)))
    weeks = q("SELECT DISTINCT week FROM schedules WHERE season=? ORDER BY week",
              (season,))["week"].tolist()
    week = c2.selectbox("Week", weeks)
    st.dataframe(q("""
        SELECT strftime(gameday,'%a %b %d') date, away_team away, away_score,
               home_team home, home_score, spread_line "spread (home)",
               total_line "o/u", home_moneyline "home ML"
        FROM schedules WHERE season=? AND week=? ORDER BY gameday, gametime
    """, (season, week)), width="stretch", hide_index=True)

# ---------- News ----------
elif page == "News":
    st.title("League news")
    src = st.radio("Source", ["All", "ESPN", "Team sites"], horizontal=True)
    where = {"All": "source IN ('espn_news','team_site')",
             "ESPN": "source = 'espn_news'",
             "Team sites": "source = 'team_site'"}[src]
    news = qnews(f"""
        SELECT strftime(published_ts,'%b %d %H:%M') at, source, teams, headline, url
        FROM news WHERE {where}
        ORDER BY published_ts DESC NULLS LAST LIMIT 50
    """)
    for r in news.itertuples():
        tag = (f"🏟️ {r.teams[0]}" if r.source == "team_site" and len(r.teams)
               else "📺 ESPN")
        st.markdown(f"**[{r.headline}]({r.url})**  \n<small>{r.at} · {tag}</small>",
                    unsafe_allow_html=True)

# ---------- Chat ----------
elif page == "Chat":
    st.title("Ask your NFL analyst")
    st.caption("Backed by Claude with direct access to your warehouse, model, "
               "Kalshi tracker, and news. First answer takes ~20–60s.")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        st.session_state.chat_session = None
    for role, text in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(text)
    prompt = st.chat_input("e.g. Who led the league in rushing in 2025?")
    if prompt:
        st.session_state.chat_history.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)
        claude_bin = shutil.which("claude")
        if not claude_bin:
            answer = "Claude Code CLI not found on PATH — chat needs it installed."
        else:
            cmd = [claude_bin, "-p", prompt, "--output-format", "json",
                   "--allowedTools", "mcp__nfl"]
            if st.session_state.chat_session:
                cmd += ["--resume", st.session_state.chat_session]
            with st.chat_message("assistant"):
                with st.spinner("Analyzing…"):
                    try:
                        r = subprocess.run(cmd, capture_output=True, text=True,
                                           timeout=300, cwd=str(ROOT))
                        js = json.loads(r.stdout)
                        answer = js.get("result", "(no answer)")
                        st.session_state.chat_session = js.get("session_id")
                    except Exception as e:
                        answer = f"Chat error: {e}"
                st.markdown(answer)
        st.session_state.chat_history.append(("assistant", answer))
