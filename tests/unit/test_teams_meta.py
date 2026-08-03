from nfl_analytics import teams_meta


def test_exactly_32_teams():
    assert len(teams_meta.TEAMS) == 32


def test_eight_divisions_of_four():
    assert len(teams_meta.DIVISIONS) == 8
    for div, codes in teams_meta.DIVISIONS.items():
        assert len(codes) == 4, f"{div} has {len(codes)} teams"


def test_colors_are_hex():
    for code in teams_meta.TEAMS:
        c = teams_meta.color(code)
        assert c.startswith("#") and len(c) == 7
        int(c[1:], 16)  # parses


def test_domains_unique():
    domains = [v[3] for v in teams_meta.TEAMS.values()]
    assert len(set(domains)) == 32


def test_logo_urls_shaped():
    url = teams_meta.logo_url("KC")
    assert url.startswith("https://") and url.endswith(".png")
