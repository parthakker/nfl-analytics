import pytest

pytestmark = pytest.mark.api


@pytest.mark.parametrize(
    "path",
    [
        "/api/matchup/2024_99_XXX_YYY",
        "/api/matchup/h2h/KC/NOPE",
        "/api/knowledge/not-a-chapter",
        "/api/knowledge/..%2F..%2Fsecrets",
        "/api/teams/NOPE",
        "/api/coaches/Zzz%20Nobody",
        "/api/referees/999999",
    ],
)
def test_unknowns_are_404(client, path):
    assert client.get(path).status_code == 404


def test_h2h_rejects_bad_params(client):
    assert client.get("/api/matchup/h2h/KC/LV?season_type=BOTH").status_code == 400
    assert client.get("/api/matchup/h2h/KC/LV?site=moon").status_code == 400


def test_leaders_rejects_unknown_cat(client):
    r = client.get("/api/leaders?cat=definitely_not_a_cat")
    assert r.status_code in (400, 404, 422)
