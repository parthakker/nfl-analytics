"""The pbp weather free-text parser (build_views.parse_weather) against known
string shapes, run on an in-memory DuckDB."""

import duckdb
import pytest

from tests.helpers import load_build_views

CASES = [
    (
        "Cloudy, 80% chance of rain Temp: 64° F, Humidity: 93%, Wind: South 9 mph",
        {
            "sky": "Cloudy, 80% chance of rain",
            "temp_f": 64,
            "humidity_pct": 93,
            "wind_dir": "South",
            "wind_mph": 9,
        },
    ),
    (
        "Sunny Temp: 75° F, Humidity: 40%, Wind: NNW 5-10 mph",
        {"temp_f": 75, "wind_dir": "NNW", "wind_mph": 5, "wind_mph_high": 10},
    ),
    (
        "Clear Temp: 55° F, Humidity: 60%, Wind: W 12 mph, Gusts up to 25 mph",
        {"gust_mph": 25, "wind_mph": 12},
    ),
    (
        "Controlled Climate Temp: 68° F, Humidity: 70%, Wind:  mph",
        {"temp_f": 68, "wind_mph": None, "is_indoor_note": True},
    ),
    ("Temp: ° F, Wind:  mph", {"temp_f": None, "wind_mph": None, "sky": None}),
    (
        "N/A (Indoors) Temp: 70° F, Humidity: 35%, Wind: 0 mph",
        {"is_indoor_note": True, "wind_mph": 0},
    ),
]


@pytest.fixture(scope="module")
def parsed():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE play_by_play (game_id VARCHAR, weather VARCHAR)")
    con.executemany(
        "INSERT INTO play_by_play VALUES (?, ?)", [(f"g{i}", w) for i, (w, _) in enumerate(CASES)]
    )
    bv = load_build_views()
    bv.parse_weather(con)
    rows = con.execute("SELECT * FROM game_weather_parsed ORDER BY game_id").fetchall()
    cols = [d[0] for d in con.execute("SELECT * FROM game_weather_parsed LIMIT 0").description]
    return [dict(zip(cols, r, strict=False)) for r in rows]


@pytest.mark.parametrize("idx", range(len(CASES)))
def test_case(parsed, idx):
    raw, expected = CASES[idx]
    row = next(r for r in parsed if r["weather_raw"] == raw)
    for key, want in expected.items():
        assert row[key] == want, f"{key}: got {row[key]!r}, want {want!r} for {raw!r}"
