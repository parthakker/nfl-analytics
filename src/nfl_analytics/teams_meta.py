"""Static metadata for all 32 teams: names, divisions, official-site domains
(for RSS news), ESPN logo codes, and primary brand colors.

One source of truth shared by the dashboard and the news poller.
Logo URL pattern: https://a.espncdn.com/i/teamlogos/nfl/500/{espn}.png
Team-site RSS pattern: https://www.{domain}/rss/news
"""

# code: (full name, conference, division, domain, espn_logo_code, primary_hex)
TEAMS = {
    "BUF": ("Buffalo Bills", "AFC", "East", "buffalobills.com", "buf", "#00338D"),
    "MIA": ("Miami Dolphins", "AFC", "East", "miamidolphins.com", "mia", "#008E97"),
    "NE":  ("New England Patriots", "AFC", "East", "patriots.com", "ne", "#002244"),
    "NYJ": ("New York Jets", "AFC", "East", "newyorkjets.com", "nyj", "#125740"),
    "BAL": ("Baltimore Ravens", "AFC", "North", "baltimoreravens.com", "bal", "#241773"),
    "CIN": ("Cincinnati Bengals", "AFC", "North", "bengals.com", "cin", "#FB4F14"),
    "CLE": ("Cleveland Browns", "AFC", "North", "clevelandbrowns.com", "cle", "#311D00"),
    "PIT": ("Pittsburgh Steelers", "AFC", "North", "steelers.com", "pit", "#FFB612"),
    "HOU": ("Houston Texans", "AFC", "South", "houstontexans.com", "hou", "#03202F"),
    "IND": ("Indianapolis Colts", "AFC", "South", "colts.com", "ind", "#002C5F"),
    "JAX": ("Jacksonville Jaguars", "AFC", "South", "jaguars.com", "jax", "#006778"),
    "TEN": ("Tennessee Titans", "AFC", "South", "tennesseetitans.com", "ten", "#0C2340"),
    "DEN": ("Denver Broncos", "AFC", "West", "denverbroncos.com", "den", "#FB4F14"),
    "KC":  ("Kansas City Chiefs", "AFC", "West", "chiefs.com", "kc", "#E31837"),
    "LAC": ("Los Angeles Chargers", "AFC", "West", "chargers.com", "lac", "#0080C6"),
    "LV":  ("Las Vegas Raiders", "AFC", "West", "raiders.com", "lv", "#000000"),
    "DAL": ("Dallas Cowboys", "NFC", "East", "dallascowboys.com", "dal", "#003594"),
    "NYG": ("New York Giants", "NFC", "East", "giants.com", "nyg", "#0B2265"),
    "PHI": ("Philadelphia Eagles", "NFC", "East", "philadelphiaeagles.com", "phi", "#004C54"),
    "WAS": ("Washington Commanders", "NFC", "East", "commanders.com", "wsh", "#5A1414"),
    "CHI": ("Chicago Bears", "NFC", "North", "chicagobears.com", "chi", "#0B162A"),
    "DET": ("Detroit Lions", "NFC", "North", "detroitlions.com", "det", "#0076B6"),
    "GB":  ("Green Bay Packers", "NFC", "North", "packers.com", "gb", "#203731"),
    "MIN": ("Minnesota Vikings", "NFC", "North", "vikings.com", "min", "#4F2683"),
    "ATL": ("Atlanta Falcons", "NFC", "South", "atlantafalcons.com", "atl", "#A71930"),
    "CAR": ("Carolina Panthers", "NFC", "South", "panthers.com", "car", "#0085CA"),
    "NO":  ("New Orleans Saints", "NFC", "South", "neworleanssaints.com", "no", "#D3BC8D"),
    "TB":  ("Tampa Bay Buccaneers", "NFC", "South", "buccaneers.com", "tb", "#D50A0A"),
    "ARI": ("Arizona Cardinals", "NFC", "West", "azcardinals.com", "ari", "#97233F"),
    "LA":  ("Los Angeles Rams", "NFC", "West", "therams.com", "lar", "#003594"),
    "SEA": ("Seattle Seahawks", "NFC", "West", "seahawks.com", "sea", "#002244"),
    "SF":  ("San Francisco 49ers", "NFC", "West", "49ers.com", "sf", "#AA0000"),
}

DIVISIONS = {}
for _code, (_n, conf, div, *_rest) in TEAMS.items():
    DIVISIONS.setdefault(f"{conf} {div}", []).append(_code)


def name(code: str) -> str:
    return TEAMS[code][0]


def logo_url(code: str, size: int = 500) -> str:
    return f"https://a.espncdn.com/i/teamlogos/nfl/{size}/{TEAMS[code][4]}.png"


def rss_url(code: str) -> str:
    return f"https://www.{TEAMS[code][3]}/rss/news"


def color(code: str) -> str:
    return TEAMS[code][5]
