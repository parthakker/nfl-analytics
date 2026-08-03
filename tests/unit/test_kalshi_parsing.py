from nfl_analytics.kalshi import _f, parse_event_ticker


def test_parse_game_ticker():
    d = parse_event_ticker("KXNFLGAME-25SEP04DALPHI")
    assert d.get("away_team") == "DAL"
    assert d.get("home_team") == "PHI"
    assert d.get("event_date") is not None


def test_parse_unknown_ticker_is_graceful():
    d = parse_event_ticker("KXNFLWINS-GB-25")
    assert isinstance(d, dict)  # never raises


def test_f_coercion():
    assert _f("3.5") == 3.5
    assert _f(None) is None
    assert _f("") is None
