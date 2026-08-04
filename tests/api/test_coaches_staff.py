"""Contract tests for the role-aware coaches API + staff roster."""

import pytest

pytestmark = pytest.mark.api


def test_staff_roster_complete(client):
    d = client.get("/api/coaches").json()
    staff = d["staff"]
    assert len(staff) == 63  # 32 OCs + 31 DCs (TB has no DC by design)
    assert all(s["name"] and s["about"] and s["scheme_family"] for s in staff)
    assert {s["role"] for s in staff} == {"OC", "DC"}
    assert len({s["team"] for s in staff if s["role"] == "OC"}) == 32


def test_hc_detail_has_about_and_staff(client):
    d = client.get("/api/coaches/Andy%20Reid").json()
    assert d["role"] == "HC"
    assert d["about"]
    assert d["staff"]["oc"]["name"] and d["staff"]["dc"]["name"]
    assert d["scheme"]["offense_scheme"]["knowledge"].startswith("offensive-scheme-families")


def test_meta_only_hc_renders(client):
    """New 2026 hires have no warehouse history but must not 404."""
    d = client.get("/api/coaches/Jesse%20Minter").json()
    assert d["role"] == "HC" and d["seasons"] == [] and d["about"]


def test_coordinator_detail(client):
    d = client.get("/api/coaches/Steve%20Spagnuolo?role=DC").json()
    assert d["role"] == "DC" and d["current_team"] == "KC"
    assert d["unit_seasons"] and {"season", "epa", "rank"} <= set(d["unit_seasons"][0])
    assert d["scheme"]["knowledge"]


def test_ex_hc_coordinator_prefers_hc_without_role(client):
    d = client.get("/api/coaches/Steve%20Spagnuolo").json()
    assert d["role"] == "HC"
    assert d["coordinator_role"] == {"role": "DC", "team": "KC"}


def test_bad_role_400_and_unknown_404(client):
    assert client.get("/api/coaches/Tommy%20Rees?role=QB").status_code == 400
    assert client.get("/api/coaches/Zzz%20Nobody").status_code == 404
